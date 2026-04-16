from django import template

register = template.Library()


@register.filter
def split(value, delimiter=','):
    """Split a string by a delimiter and return a list of stripped, non-empty parts."""
    if not value:
        return []
    return [part.strip() for part in value.split(delimiter) if part.strip()]
