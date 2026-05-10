"""
Quản lý template tin nhắn gửi qua NetChat.

Template được lưu trong bảng SystemConfig (key/value). Nếu chưa có cấu hình
trong DB thì rơi về DEFAULT định nghĩa ở dưới.

Biến trong template viết theo cú pháp `{ten_bien}`. Biến không tồn tại sẽ
được giữ nguyên (không gây crash) — xem `render_template()`.
"""

import re

from .models import SystemConfig


# Khóa SystemConfig
KEY_OTP = 'msg_template_otp'
KEY_MEAL = 'msg_template_meal'


# Template mặc định (giữ nguyên nội dung gốc trong code cũ)
DEFAULT_OTP = (
    "🔒 **Mã xác thực đăng nhập của bạn là: {otp_code}**\n\n"
    "Mã có hiệu lực trong 10 phút. Vui lòng không chia sẻ mã này cho bất kỳ ai."
)

DEFAULT_MEAL = (
    "Xin chào **{full_name}**,\n\n"
    "🍽️ Hệ thống xác nhận bạn đã đăng ký **{meal_name}** "
    "ngày **{target_date}** tại **{kitchen_name}**.\n"
    "Chúc bạn ngon miệng!"
)


# Mô tả các biến cho UI cấu hình (key -> label tiếng Việt)
VARS_OTP = [
    ('otp_code', 'Mã OTP 6 số'),
    ('employee_code', 'Mã nhân viên'),
    ('full_name', 'Họ và tên người nhận'),
]

VARS_MEAL = [
    ('full_name', 'Họ và tên người nhận'),
    ('employee_code', 'Mã nhân viên'),
    ('meal_name', 'Tên bữa ăn (sáng/trưa/tối)'),
    ('target_date', 'Ngày ăn'),
    ('kitchen_name', 'Tên bếp'),
]


_VAR_PATTERN = re.compile(r'\{(\w+)\}')


def render_template(template_str, **values):
    """Thay thế {bien} trong template bằng giá trị tương ứng.

    Biến không có trong `values` sẽ được giữ nguyên — tránh crash khi admin
    gõ sai tên biến.
    """
    if not template_str:
        return ''

    def _replace(match):
        key = match.group(1)
        if key in values:
            return str(values[key])
        return match.group(0)

    return _VAR_PATTERN.sub(_replace, template_str)


def get_template(key, default):
    """Đọc template từ SystemConfig, fallback về default nếu chưa cấu hình."""
    cfg = SystemConfig.objects.filter(key=key).first()
    if cfg and cfg.value:
        return cfg.value
    return default


def get_otp_template():
    return get_template(KEY_OTP, DEFAULT_OTP)


def get_meal_template():
    return get_template(KEY_MEAL, DEFAULT_MEAL)
