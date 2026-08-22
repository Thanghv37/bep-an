"""Cấu hình NGÀY LÀM VIỆC TRONG TUẦN của bếp ăn.

Mặc định bếp nấu T2-T6. Nhưng có tuần đi làm bù (vd làm thêm Thứ 7) thì bếp
vẫn nấu — admin vào trang Hồ sơ tick thêm ngày đó, toàn hệ thống (dashboard,
TV, thực đơn tuần, gợi ý AI) tự hiển thị theo.

Lưu trong SystemConfig key `work_days`, value là JSON list int 0-6
(0 = Thứ 2 ... 6 = Chủ nhật) — cùng quy ước với `date.weekday()`.
"""

import json
from datetime import timedelta

from .models import SystemConfig

KEY_WORK_DAYS = 'work_days'

# T2 -> T6
DEFAULT_WORK_DAYS = [0, 1, 2, 3, 4]

WEEKDAY_LABELS = {
    0: 'Thứ 2',
    1: 'Thứ 3',
    2: 'Thứ 4',
    3: 'Thứ 5',
    4: 'Thứ 6',
    5: 'Thứ 7',
    6: 'Chủ nhật',
}

WEEKDAY_SHORT = {
    0: 'T2', 1: 'T3', 2: 'T4', 3: 'T5', 4: 'T6', 5: 'T7', 6: 'CN',
}


def get_work_days():
    """List weekday bếp có nấu (0=T2 ... 6=CN), đã sort. Mặc định T2-T6."""
    cfg = SystemConfig.objects.filter(key=KEY_WORK_DAYS).first()
    if not cfg or not cfg.value:
        return list(DEFAULT_WORK_DAYS)
    try:
        data = json.loads(cfg.value)
        if isinstance(data, list):
            cleaned = sorted({int(d) for d in data if 0 <= int(d) <= 6})
            return cleaned if cleaned else list(DEFAULT_WORK_DAYS)
    except (ValueError, TypeError):
        pass
    return list(DEFAULT_WORK_DAYS)


def set_work_days(values):
    """Lưu list weekday. `values` nhận list int / list str / chuỗi CSV.

    Nếu tick rỗng thì quay về mặc định T2-T6 (tránh trạng thái bếp không có
    ngày nào nấu → mọi trang trống trơn).
    """
    if isinstance(values, str):
        values = [v.strip() for v in values.split(',') if v.strip()]
    cleaned = sorted({
        int(v) for v in (values or [])
        if str(v).strip().isdigit() and 0 <= int(v) <= 6
    })
    if not cleaned:
        cleaned = list(DEFAULT_WORK_DAYS)
    SystemConfig.objects.update_or_create(
        key=KEY_WORK_DAYS,
        defaults={'value': json.dumps(cleaned)},
    )
    return cleaned


def is_work_day(d, work_days=None):
    """Ngày `d` bếp có nấu không."""
    days = work_days if work_days is not None else get_work_days()
    return d.weekday() in days


def week_start_of(d):
    """Thứ 2 của tuần chứa ngày `d`."""
    return d - timedelta(days=d.weekday())


def work_days_of_week(any_date, work_days=None):
    """List các ngày bếp nấu trong tuần chứa `any_date`, tăng dần."""
    days = work_days if work_days is not None else get_work_days()
    start = week_start_of(any_date)
    return [start + timedelta(days=i) for i in sorted(days)]


def work_days_next_week(today, work_days=None):
    """List các ngày bếp nấu của TUẦN SAU tính từ `today`."""
    next_monday = week_start_of(today) + timedelta(days=7)
    days = work_days if work_days is not None else get_work_days()
    return [next_monday + timedelta(days=i) for i in sorted(days)]


def work_day_labels(work_days=None):
    """List (weekday_int, 'Thứ 2') theo đúng thứ tự hiển thị."""
    days = work_days if work_days is not None else get_work_days()
    return [(i, WEEKDAY_LABELS[i]) for i in sorted(days)]
