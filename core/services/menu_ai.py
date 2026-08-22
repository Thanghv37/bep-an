import json
import logging
import re

from core.ai_config import get_genai_model

logger = logging.getLogger(__name__)

def clean_json(text):
    if not text:
        return ""
    text = text.strip()
    # Loại bỏ markdown
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # Tìm kiếm khối JSON đầu tiên (mảng hoặc đối tượng)
    match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if match:
        return match.group(1)
    return text

class MenuAIService:
    def __init__(self):
        # API key + model name lấy từ SystemConfig (UI Profile),
        # fallback env var GEMINI_API_KEY nếu DB chưa cấu hình.
        self.model = get_genai_model()

    def suggest_next_week_menu(self, available_dishes, last_week_menu_text,
                               day_names=None):
        # Ngày cần lên thực đơn lấy từ cấu hình "Ngày làm việc" (trang Hồ sơ).
        # Mặc định T2-T6; tuần đi làm bù có thể có thêm Thứ 7 / Chủ nhật.
        if not day_names:
            day_names = ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6']
        days_text = ', '.join(day_names)
        last_day = day_names[-1]
        normal_days = [d for d in day_names if d != last_day]
        normal_days_text = ', '.join(normal_days) if normal_days else '(không có)'

        prompt = f"""
        Bạn là một chuyên gia dinh dưỡng và quản lý bếp ăn công nghiệp.
        Nhiệm vụ của bạn là lập thực đơn cho tuần tới dựa trên danh sách món ăn có sẵn.

        CHỈ LẬP THỰC ĐƠN CHO ĐÚNG CÁC NGÀY SAU (không thêm, không bớt ngày nào):
        {days_text}

        DANH SÁCH MÓN ĂN CÓ SẴN (ID - Tên - Loại):
        {json.dumps(available_dishes, ensure_ascii=False)}

        THỰC ĐƠN TUẦN TRƯỚC (Để tránh lặp lại):
        {last_week_menu_text}

        HƯỚNG DẪN PHÂN LOẠI MÓN ĂN TRONG LOẠI "main":
        - "Món Cơm": Các món có tên chứa chữ "Cơm" (Ví dụ: Cơm trắng, Cơm tám...).
        - "Món Nước/Sợi": Các món như Bún, Phở, Mì, Miến, Hủ tiếu, Bánh canh...
        - "Món Mặn": Các món còn lại trong loại "main" dùng để ăn với cơm (Ví dụ: Thịt rang, Cá kho, Bò xào, Gà chiên...).

        YÊU CẦU CHI TIẾT CHO TỪNG NGÀY:
        1. CÁC NGÀY {normal_days_text} (Thực đơn cơm): Mỗi ngày chọn ĐÚNG 6 món sau:
           - 01 Món Cơm (từ loại main).
           - 02 Món Mặn khác nhau (từ loại main - KHÔNG chọn món Nước/Sợi ở đây).
           - 02 Món phụ (side).
           - 01 Món canh (soup).
           - 01 Món tráng miệng (dessert).

        2. RIÊNG NGÀY CUỐI TUẦN LÀM VIỆC — {last_day} (Ngày đổi món): chọn ĐÚNG 2 món sau:
           - 01 Món Nước/Sợi duy nhất (từ loại main - Ví dụ: Bún bò, Phở gà... KHÔNG chọn cơm).
           - 01 Món tráng miệng (dessert).
           - ({last_day} không cần món phụ và món canh).

        TIÊU CHÍ CHỌN MÓN:
        - KHÔNG trùng lặp các "Món Mặn" và "Món Nước/Sợi" của tuần trước.
        - Đảm bảo thực đơn đa dạng: Không chọn cùng một loại thịt (ví dụ thịt lợn) cho cả 2 món mặn trong cùng 1 ngày.

        KẾT QUẢ TRẢ VỀ:
        Trả về JSON duy nhất (chỉ trả về mảng, KHÔNG giải thích, KHÔNG có trường reason).
        Trường "day" phải ghi ĐÚNG một trong các giá trị: {days_text}.
        [
            {{
                "day": "{day_names[0]}",
                "dish_ids": [id_com, id_man1, id_man2, id_phu1, id_phu2, id_canh, id_trangmieng]
            }},
            ... đủ {len(day_names)} ngày, cho đến {last_day}
        ]
        """

        try:
            response = self.model.generate_content(prompt)
            raw_text = response.text.strip()
            
            # IN LOG RA TERMINAL ĐỂ DEBUG
            print("\n" + "="*50)
            print("AI MENU SUGGESTION RAW RESPONSE:")
            print(raw_text)
            print("="*50 + "\n")
            
            cleaned_content = clean_json(raw_text)
            return json.loads(cleaned_content)
        except Exception as e:
            logger.error(f"Error in Gemini Menu Suggestion: {str(e)}")
            print(f"DEBUG - AI ERROR: {str(e)}")
            return None
