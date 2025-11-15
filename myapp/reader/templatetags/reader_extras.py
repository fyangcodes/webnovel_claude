"""
Custom template filters and tags for the reader app.

This module provides template utilities for working with hierarchical
taxonomy data structures (sections, genres, tags).
"""

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary by key.
    
    Usage in templates:
        {{ my_dict|get_item:key_variable }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def get_sub_genres(sub_genres_dict, parent_id):
    """
    Get sub-genres for a parent genre from the hierarchical structure.
    
    Usage in templates:
        {% for sub_genre in section_data.sub_genres|get_sub_genres:parent_genre.id %}
    """
    if sub_genres_dict is None:
        return []
    return sub_genres_dict.get(parent_id, [])


@register.simple_tag
def query_transform(request, **kwargs):
    """
    Transform the current query string by adding/updating parameters.
    
    Usage in templates:
        <a href="?{% query_transform request section='bl' page=None %}">
    
    Use key=None to remove a parameter.
    """
    updated = request.GET.copy()
    for key, value in kwargs.items():
        if value is None:
            updated.pop(key, None)  # Remove parameter
        else:
            updated[key] = value
    return updated.urlencode()
