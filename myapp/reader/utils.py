"""
Helper functions for accessing style configurations.

These functions provide a clean interface for accessing StyleConfig
without creating dependencies in the books app.
"""

from django.contrib.contenttypes.models import ContentType
from reader.models import StyleConfig


def get_style_for_object(obj):
    """
    Get StyleConfig for any object.

    This function uses defensive programming to never raise exceptions,
    making it safe to use in templates and views.

    Args:
        obj: Any Django model instance

    Returns:
        StyleConfig instance or None

    Example:
        from books.models import Section
        from reader.utils import get_style_for_object

        fiction = Section.objects.get(slug='fiction')
        style = get_style_for_object(fiction)
        if style:
            print(f"Color: {style.color}")
            print(f"Icon: {style.icon}")
    """
    if obj is None:
        return None

    try:
        content_type = ContentType.objects.get_for_model(obj.__class__)
        # Use filter().first() instead of get() for defensive programming:
        # - Never raises DoesNotExist exception
        # - Never raises MultipleObjectsReturned exception
        # - Returns None if no match found
        # - Safe to use in templates
        return StyleConfig.objects.filter(
            content_type=content_type,
            object_id=obj.pk
        ).first()
    except Exception:
        # Catch any unexpected errors (e.g., database issues)
        return None


def get_styles_for_queryset(queryset_or_list):
    """
    Efficiently prefetch styles for a queryset or list of objects.

    This function optimizes database queries when you need styles for
    multiple objects at once (e.g., displaying a list of sections).

    Args:
        queryset_or_list: Django QuerySet or list of model instances

    Returns:
        dict mapping object.pk to StyleConfig

    Example:
        from books.models import Section
        from reader.utils import get_styles_for_queryset

        sections = Section.objects.all()
        styles = get_styles_for_queryset(sections)

        for section in sections:
            style = styles.get(section.pk)
            if style:
                print(f"{section.name}: {style.color}")
    """
    if not queryset_or_list:
        return {}

    try:
        # Handle both queryset and list
        if isinstance(queryset_or_list, list):
            # It's a list - get model class from first item
            if not queryset_or_list:
                return {}
            model_class = queryset_or_list[0].__class__
            object_ids = [obj.pk for obj in queryset_or_list]
        else:
            # It's a queryset
            model_class = queryset_or_list.model
            object_ids = list(queryset_or_list.values_list('pk', flat=True))

        content_type = ContentType.objects.get_for_model(model_class)
        styles = StyleConfig.objects.filter(
            content_type=content_type,
            object_id__in=object_ids
        )

        # Create mapping: object_id -> StyleConfig
        return {style.object_id: style for style in styles}
    except Exception:
        # Return empty dict on any error
        return {}


def create_style_for_object(obj, color='', icon='', custom_styles=None):
    """
    Create or update StyleConfig for an object.

    Args:
        obj: Any Django model instance
        color: Hex color code (e.g., '#3498db')
        icon: FontAwesome icon class (e.g., 'fas fa-book')
        custom_styles: Dict of additional CSS properties

    Returns:
        StyleConfig instance or None

    Example:
        from books.models import Section
        from reader.utils import create_style_for_object

        fiction = Section.objects.get(slug='fiction')
        style = create_style_for_object(
            fiction,
            color='#3498db',
            icon='fas fa-book',
            custom_styles={'font_weight': '600'}
        )
    """
    if obj is None:
        return None

    try:
        content_type = ContentType.objects.get_for_model(obj.__class__)

        # Use update_or_create for idempotency
        style, created = StyleConfig.objects.update_or_create(
            content_type=content_type,
            object_id=obj.pk,
            defaults={
                'color': color,
                'icon': icon,
                'custom_styles': custom_styles or {}
            }
        )
        return style
    except Exception:
        return None
