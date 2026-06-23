import json
import re

from core.ai_config import get_genai_model


def clean_json(text):
    text = text.strip()

    # Gemini đôi khi trả về ```json ... ```
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    return json.loads(text)


def estimate_nutrition(menu_data):
    compact_menu = json.dumps(
        menu_data,
        ensure_ascii=False,
        separators=(",", ":")
    )

    print("===== AI MENU DATA =====")
    print(compact_menu)
    print("===== AI MENU DATA LENGTH =====")
    print(len(compact_menu))

    prompt = f"""
Bạn là AI dinh dưỡng thân thiện cho bếp ăn công ty.

Ước tính tổng kcal/suất dựa trên nguyên liệu và gram/người, và nhận xét về thực đơn HÔM NAY.

Yêu cầu:
- Giọng văn thân thiện, gần gũi, dễ hiểu cho người lao động; KHÔNG dùng thuật ngữ kỹ thuật.
- summary: khoảng 3 câu, phân tích CỤ THỂ thực đơn hôm nay — nhắc tên vài món tiêu biểu,
  nhận xét sự cân đối giữa chất đạm / rau xanh / tinh bột, và kèm một lời khuyên ăn uống ngắn.
- summary khoảng 250-300 ký tự, viết liền 1 đoạn, KHÔNG xuống dòng, KHÔNG markdown.
- chỉ trả JSON

Menu:{compact_menu}

JSON:
{{
  "total_kcal": number,
  "level": "Thấp|Cân bằng|Cao",
  "summary": "khoảng 3 câu phân tích thực đơn hôm nay"
}}
"""

    try:
        model = get_genai_model()
        response = model.generate_content(prompt)

        return clean_json(response.text)

    except Exception as e:
        print("AI ERROR:", e)

        return {
            "total_kcal": 0,
            "level": "Không xác định",
            "summary": "AI tạm thời chưa khả dụng, vui lòng thử lại sau."
        }