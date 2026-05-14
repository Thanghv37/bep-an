from django import template

register = template.Library()


def _vn_number(value, decimals=2):
    """Format số kiểu VN: dấu phẩy thập phân, dấu chấm hàng nghìn."""
    fmt = f"{{:,.{decimals}f}}".format(value)
    return fmt.replace(",", "X").replace(".", ",").replace("X", ".")


@register.filter
def format_weight(value, unit='g'):
    """Format khối lượng theo đơn vị nguyên liệu.

    - unit = 'g' (mặc định): tự đổi sang kg nếu >= 1000.
    - unit = 'ml': tự đổi sang l nếu >= 1000.
    - unit khác (quả, củ, cái, lít, kg, ...): giữ nguyên đơn vị, format 2 số thập phân.
    - unit rỗng: dùng như 'g' để tương thích code cũ.
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value

    unit = (unit or 'g').strip().lower()

    if unit in ('g', ''):
        if value >= 1000:
            return _vn_number(value / 1000) + ' kg'
        return _vn_number(value) + ' g'

    if unit == 'ml':
        if value >= 1000:
            return _vn_number(value / 1000) + ' l'
        return _vn_number(value) + ' ml'

    # Các đơn vị khác (quả, củ, cái, lít, kg...) — giữ nguyên đơn vị gốc.
    # Số nguyên thì bỏ phần thập phân thừa cho gọn (vd 7.00 → "7").
    if value == int(value):
        return f"{int(value):,}".replace(",", ".") + f" {unit}"
    return _vn_number(value) + f" {unit}"
