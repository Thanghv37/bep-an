import os
import json
import re
import google.generativeai as genai


# Ưu tiên lấy từ biến môi trường.
# Nếu test local nhanh thì có thể hardcode tạm, nhưng không nên push lên Git.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)


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
Bạn là AI dinh dưỡng cho bếp ăn công ty.

Ước tính tổng kcal/suất dựa trên nguyên liệu và gram/người.

Yêu cầu:
- Trả lời NGẮN GỌN
- summary tối đa 2 câu
- tối đa 150 ký tự
- không giải thích dài dòng
- không markdown
- chỉ trả JSON

Menu:{compact_menu}

JSON:
{{
  "total_kcal": number,
  "level": "Thấp|Cân bằng|Cao",
  "summary": "ngắn gọn"
}}
"""

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)

        return clean_json(response.text)

    except Exception as e:
        print("AI ERROR:", e)

        return {
            "total_kcal": 0,
            "level": "Không xác định",
            "summary": "AI tạm thời chưa khả dụng, vui lòng thử lại sau."
        }