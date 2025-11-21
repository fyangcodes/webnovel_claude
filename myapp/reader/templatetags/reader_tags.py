"""
Template tags for reader app styling.

Provides template tags and filters for accessing StyleConfig
in templates without creating dependencies in the books app.
"""

from django import template
from reader.utils import get_style_for_object

register = template.Library()


@register.simple_tag
def get_style(obj):
    """
    Get style configuration for an object.

    Usage in template:
        {% load reader_tags %}
        {% get_style section as style %}
        {% if style %}
            <div style="background-color: {{ style.color }};">
        {% endif %}

    Args:
        obj: Any Django model instance

    Returns:
        StyleConfig instance or None
    """
    return get_style_for_object(obj)


@register.filter
def has_style(obj):
    """
    Check if object has a style configuration.

    Usage:
        {% load reader_tags %}
        {% if section|has_style %}
            ...
        {% endif %}

    Args:
        obj: Any Django model instance

    Returns:
        bool: True if object has a StyleConfig, False otherwise
    """
    style = get_style_for_object(obj)
    return style is not None


@register.filter
def style_color(obj):
    """
    Get color from object's style.

    Usage:
        {% load reader_tags %}
        <div style="background-color: {{ section|style_color }};">

    Args:
        obj: Any Django model instance

    Returns:
        str: Hex color code or empty string if no style/color
    """
    style = get_style_for_object(obj)
    return style.color if style else ''


@register.filter
def style_icon(obj):
    """
    Get icon from object's style.

    Usage:
        {% load reader_tags %}
        <i class="{{ section|style_icon }}"></i>

    Args:
        obj: Any Django model instance

    Returns:
        str: FontAwesome icon class or empty string if no style/icon
    """
    style = get_style_for_object(obj)
    return style.icon if style else ''


@register.filter
def style_property(obj, key):
    """
    Get a custom style property from object's style.

    Usage:
        {% load reader_tags %}
        <div style="font-weight: {{ section|style_property:'font_weight' }};">

    Args:
        obj: Any Django model instance
        key: Property key from custom_styles JSON field

    Returns:
        The property value or empty string if not found
    """
    style = get_style_for_object(obj)
    if style:
        return style.get_style_property(key, '')
    return ''
