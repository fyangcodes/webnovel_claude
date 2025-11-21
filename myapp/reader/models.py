"""
Reader app models.

This module contains models related to the reader/presentation layer.
"""

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from books.models.base import TimeStampedModel


class StyleConfig(TimeStampedModel):
    """
    Generic UI styling configuration for any model.

    Uses Django's ContentType framework to provide styling for any model
    without creating tight coupling. This allows the reader app to provide
    presentation-layer styling while keeping the books app independent.

    Example usage:
        # Create style for a Section
        from django.contrib.contenttypes.models import ContentType
        from books.models import Section
        from reader.models import StyleConfig

        fiction = Section.objects.get(slug='fiction')
        content_type = ContentType.objects.get_for_model(Section)

        style = StyleConfig.objects.create(
            content_type=content_type,
            object_id=fiction.pk,
            color='#3498db',
            icon='fas fa-book',
            custom_styles={'font_weight': '600', 'hover_brightness': '1.1'}
        )
    """

    # Generic relation to any model
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Type of object this style applies to"
    )
    object_id = models.PositiveIntegerField(
        help_text="ID of the object this style applies to"
    )
    content_object = GenericForeignKey('content_type', 'object_id')

    # Color styling
    color = models.CharField(
        max_length=7,
        blank=True,
        default='',
        help_text="Primary color in hex format (e.g., '#FF5733')"
    )

    # Icon styling
    icon = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="FontAwesome icon class (e.g., 'fas fa-book')"
    )

    # Extensible styling via JSON
    custom_styles = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional CSS properties: {font_weight, border_radius, hover_color, etc.}"
    )

    class Meta:
        verbose_name = "Style Configuration"
        verbose_name_plural = "Style Configurations"
        unique_together = [['content_type', 'object_id']]
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"Style for {self.content_object} (color: {self.color or 'default'})"

    def get_style_property(self, key, default=None):
        """
        Get a custom style property with fallback.

        Args:
            key: The style property key to retrieve
            default: Default value if key doesn't exist

        Returns:
            The style property value or default
        """
        return self.custom_styles.get(key, default)

    def set_style_property(self, key, value):
        """
        Set a custom style property.

        Args:
            key: The style property key
            value: The value to set
        """
        self.custom_styles[key] = value
