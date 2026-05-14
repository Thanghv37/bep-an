"""Quản lý danh sách option cho dropdown "Bữa ăn" và "Tên bếp ăn" trong form
Thêm người đăng kí. Lưu trong SystemConfig dưới dạng JSON list-of-strings.
"""

import json

from core.models import SystemConfig


KEY_MEAL_OPTIONS = 'registration_meal_options'
KEY_KITCHEN_OPTIONS = 'registration_kitchen_options'

DEFAULT_MEAL_OPTIONS = ['Bữa sáng', 'Bữa trưa', 'Bữa tối']

DEFAULT_KITCHEN_OPTIONS = [
    'VTNet - Bếp ăn khu vực 2 (Đà Nẵng)',
    'VTNet - Bếp ăn khối cơ quan (Tòa nhà Thái Bình)',
    'Bếp ăn học viện Viettel (Thạch Thất)',
]


def _load_list(key, default):
    cfg = SystemConfig.objects.filter(key=key).first()
    if not cfg or not cfg.value:
        return list(default)
    try:
        value = json.loads(cfg.value)
        if isinstance(value, list):
            # Bỏ entry rỗng / không phải string.
            return [str(item).strip() for item in value if str(item).strip()]
    except (ValueError, TypeError):
        pass
    return list(default)


def _save_list(key, items):
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    # Khử trùng nhưng giữ thứ tự xuất hiện.
    seen = set()
    deduped = []
    for item in cleaned:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    SystemConfig.objects.update_or_create(
        key=key,
        defaults={'value': json.dumps(deduped, ensure_ascii=False)},
    )
    return deduped


def get_meal_options():
    return _load_list(KEY_MEAL_OPTIONS, DEFAULT_MEAL_OPTIONS)


def get_kitchen_options():
    return _load_list(KEY_KITCHEN_OPTIONS, DEFAULT_KITCHEN_OPTIONS)


def set_meal_options(items):
    return _save_list(KEY_MEAL_OPTIONS, items)


def set_kitchen_options(items):
    return _save_list(KEY_KITCHEN_OPTIONS, items)
