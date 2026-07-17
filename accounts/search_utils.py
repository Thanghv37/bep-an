"""Tiện ích tìm kiếm người dùng theo 3 cách: tên / username / mã NV.

`username` ở đây = phần trước dấu @ của email (vd `vuongtv@viettel.com.vn`
-> `vuongtv`) — cùng thứ mà ô "Mã NV hoặc Username" ở form đăng kí chấp nhận.

Dùng `split_part(email, '@', 1)` của PostgreSQL để lấy đúng local part; KHÔNG
match thẳng vào cả email vì domain giống nhau ở mọi người (gõ "viettel" sẽ ra
toàn bộ danh sách).
"""

from django.db.models import CharField, F, Func, Value

from .models import UserProfile


class SplitPart(Func):
    """PostgreSQL `split_part(text, delimiter, n)`."""
    function = 'split_part'
    output_field = CharField()


def username_expr(email_field='email'):
    """Expression lấy username (local part) từ field email chỉ định.

    `email_field` là đường dẫn ORM tới field email, vd:
    - 'email'                (queryset UserProfile)
    - 'profile__email'       (queryset User)
    - 'user__profile__email' (queryset có FK tới User)
    """
    return SplitPart(F(email_field), Value('@'), Value(1))


def employee_codes_matching_username(keyword):
    """Trả về list employee_code có username chứa `keyword`.

    Dùng cho các bảng chỉ lưu employee_code (MealRegistration, AttendanceLog...)
    — không join được sang UserProfile bằng ORM vì employee_code là CharField
    chứ không phải khoá ngoại.
    """
    keyword = (keyword or '').strip()
    if not keyword:
        return []
    return list(
        UserProfile.objects
        .annotate(_uname=username_expr('email'))
        .filter(_uname__icontains=keyword)
        .exclude(employee_code='')
        .values_list('employee_code', flat=True)
    )
