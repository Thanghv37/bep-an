from django import template

register = template.Library()

@register.filter
def format_weight(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value

    if value >= 1000:
        kg = value / 1000
        return f"{kg:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " kg"

    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " g"