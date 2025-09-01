from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key) 

@register.filter(name="markdown")
def markdown_format(text):
    """Simple markdown replacement for MVP - just convert newlines to <br>"""
    return mark_safe(text.replace('\n', '<br>'))

@register.filter
def exists(value):
    """Check if a variable exists and is not None"""
    return value is not None