import os
import json
import re
import google.generativeai as genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)


def clean_json(text):
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def scan_receipt_image(file_bytes, mime_type):
    prompt = """
    Bạn là một trợ lý AI phân tích hóa đơn chi phí cho bếp ăn công ty.
    Hãy đọc hình ảnh hóa đơn/bill/biên lai đính kèm và trích xuất các thông tin sau:
    1. Tổng số tiền thanh toán (thường nằm ở dòng Tổng cộng/Thành tiền cuối cùng). Chỉ lấy số nguyên, ví dụ: 1521000.
    2. Danh sách các mặt hàng đã mua: Tên hàng, Số lượng, Đơn vị tính, Đơn giá.
    
    Yêu cầu ĐẶC BIỆT:
    - Bắt buộc trả về định dạng JSON thuần túy, KHÔNG markdown, KHÔNG text giải thích dư thừa.
    - Nếu không đọc được trường nào, hãy để null hoặc 0.
    - Cấu trúc JSON phải chính xác như sau:
    {
      "total_cost": 1521000,
      "items": [
        {
          "name": "Thịt ba chỉ",
          "quantity": 3.0,
          "unit": "kg",
          "unit_price": 147000
        },
        ...
      ]
    }
    """

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        image_part = {
            "mime_type": mime_type,
            "data": file_bytes
        }
        
        response = model.generate_content([image_part, prompt])
        
        return clean_json(response.text)

    except Exception as e:
        print("AI RECEIPT SCAN ERROR:", e)
        return {
            "total_cost": 0,
            "items": [],
            "error": str(e)
        }
