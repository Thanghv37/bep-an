from django import template

register = template.Library()


def _vn_number(value, decimals=2):
    """Format số kiểu VN: dấu phẩy thập phân, dấu chấm hàng nghìn."""
    fmt = f"{{:,.{decimals}f}}".format(value)
    return fmt.replace(",", "X").replace(".", ",").replace("X", ".")


_UNIT_ALIASES = {
    'gram': 'g',
    'kilogram': 'kg',
    'mililit': 'ml',
    'lit': 'l',
    'lít': 'l',
}


@register.filter
def format_weight(value, unit='g'):
    """Format khối lượng theo đơn vị nguyên liệu.

    - unit = 'g' / 'Gram': tự đổi sang kg nếu >= 1000.
    - unit = 'ml' / 'Ml': tự đổi sang l nếu >= 1000.
    - unit khác (Quả, Củ, Cái, Miếng, Kg, Lít...): giữ nguyên casing người dùng nhập.
    - unit rỗng: dùng như 'g' để tương thích code cũ.
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value

    raw = (unit or 'g').strip()
    key = raw.lower()
    canonical = _UNIT_ALIASES.get(key, key)

    if canonical in ('g', ''):
        if value >= 1000:
            return _vn_number(value / 1000) + ' kg'
        return _vn_number(value) + ' g'

    if canonical == 'ml':
        if value >= 1000:
            return _vn_number(value / 1000) + ' l'
        return _vn_number(value) + ' ml'

    # Các đơn vị khác — giữ nguyên casing người dùng nhập (vd "Miếng", "Lít").
    display = raw if raw else canonical
    if value == int(value):
        return f"{int(value):,}".replace(",", ".") + f" {display}"
    return _vn_number(value) + f" {display}"
