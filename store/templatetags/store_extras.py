# store/templatetags/store_extras.py
from django import template

register = template.Library()

@register.filter(name='mul')
def mul(value, arg):
    """Multiplies the value by the arg."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''