"""
Cấu hình AI Gemini cho dự án.

API key và model được lưu trong SystemConfig (chỉnh trong trang Profile của
admin). Nếu DB chưa có giá trị thì fallback về biến môi trường `GEMINI_API_KEY`
và model mặc định.
"""

import os

import google.generativeai as genai

from .models import SystemConfig


KEY_GEMINI_API_KEY = 'gemini_api_key'
KEY_GEMINI_MODEL = 'gemini_model'

DEFAULT_MODEL = 'gemini-2.5-flash'

# Danh sách model khả dụng — hiển thị trong dropdown UI. Cập nhật theo
# AI Studio (https://aistudio.google.com/app/usage) khi Google thêm/loại model.
# Sắp xếp từ mới → cũ. Các model `*-pro` yêu cầu tài khoản trả phí (free tier
# quota = 0); `*-flash` / `*-flash-lite` dùng OK trên free tier.
AVAILABLE_MODELS = [
    'gemini-3.1-pro',
    'gemini-3.1-flash-lite',
    'gemini-3-flash',
    'gemini-2.5-pro',
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
]


def get_gemini_api_key():
    cfg = SystemConfig.objects.filter(key=KEY_GEMINI_API_KEY).first()
    if cfg and cfg.value:
        return cfg.value
    return os.getenv("GEMINI_API_KEY", "")


def get_gemini_model():
    cfg = SystemConfig.objects.filter(key=KEY_GEMINI_MODEL).first()
    if cfg and cfg.value:
        return cfg.value
    return DEFAULT_MODEL


def get_genai_model():
    """Trả về một `GenerativeModel` đã cấu hình API key + model name từ DB.

    Gọi mỗi lần cần dùng AI để luôn pick up cấu hình mới nhất (admin có thể
    đổi key/model giữa chừng mà không cần restart server).
    """
    api_key = get_gemini_api_key()
    if api_key:
        genai.configure(api_key=api_key)
    return genai.GenerativeModel(get_gemini_model())
