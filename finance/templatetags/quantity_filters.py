from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


def clean_decimal(value):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value

    if d == d.to_integral():
        return str(int(d))

    return str(d.normalize()).replace('.', ',')


@register.filter
def smart_quantity(value, unit=''):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value

    unit = str(unit or '').lower()

    if unit == 'g' and d > 1000:
        kg_value = d / Decimal('1000')
        return clean_decimal(kg_value)

    return clean_decimal(d)


@register.filter
def smart_unit(value, unit=''):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return unit

    unit = str(unit or '')

    if unit.lower() == 'g' and d > 1000:
        return 'kg'

    return unit