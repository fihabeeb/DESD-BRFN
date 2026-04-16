from django import template

register = template.Library()

@register.filter
def sum_attribute(queryset, attribute):
    """Sum a list of objects by attribute name"""
    if not queryset:
        return 0
    return sum(getattr(obj, attribute, 0) for obj in queryset)