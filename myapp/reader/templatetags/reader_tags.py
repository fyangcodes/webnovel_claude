"""
Template tags for reader app styling.

Provides template tags and filters for accessing StyleConfig
in templates without creating dependencies in the books app.
"""

from django import template
from reader.utils import get_style_for_object

register = template.Library()


@register.simple_tag(takes_context=True)
def get_style(context, obj):
    """
    Get style configuration for an object.

    OPTIMIZED: Uses pre-fetched styles from context instead of querying.
    Falls back to query only if not in context (backwards compatible).

    Usage in template:
        {% load reader_tags %}
        {% get_style section as style %}
        {% if style %}
            <div style="background-color: {{ style.color }};">
        {% endif %}

    Args:
        context: Template context (automatically passed when takes_context=True)
        obj: Any Django model instance

    Returns:
        StyleConfig instance or None
    """
    if obj is None:
        return None

    # Try to get from pre-fetched context data
    obj_id = obj.pk

    # Check section_styles
    section_styles = context.get('section_styles', {})
    if obj_id in section_styles:
        return section_styles[obj_id]

    # Check genre_styles (flat list)
    genre_styles = context.get('genre_styles', {})
    if obj_id in genre_styles:
        return genre_styles[obj_id]

    # Check hierarchical_genre_styles
    hierarchical_styles = context.get('hierarchical_genre_styles', {})
    if obj_id in hierarchical_styles:
        return hierarchical_styles[obj_id]

    # Check tag_styles
    tag_styles = context.get('tag_styles', {})
    if obj_id in tag_styles:
        return tag_styles[obj_id]

    # Fallback: Query database (backwards compatible)
    # This ensures tag still works if prefetch not done
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
    # Check for cached style first (from view prefetch)
    if hasattr(obj, '_cached_style'):
        return obj._cached_style is not None

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
    # Check for cached style first (from view prefetch)
    if hasattr(obj, '_cached_style'):
        style = obj._cached_style
        return style.color if style else ''

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
    # Check for cached style first (from view prefetch)
    if hasattr(obj, '_cached_style'):
        style = obj._cached_style
        return style.icon if style else ''

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
