"""
Base models for the books app.
"""
from django.db import models
from django.utils.text import slugify


class SlugGeneratorMixin:
    """Mixin to generate unique slugs with automatic conflict resolution.

    Used by Book and Chapter models to generate unique slugs with UUID suffix
    when conflicts occur. This is different from LocalizationModel's simple
    slug generation which just uses slugify without conflict resolution.
    """

    def generate_unique_slug(self, base_slug, filter_kwargs=None):
        import uuid

        filter_kwargs = filter_kwargs or {}
        model_class = self.__class__

        # Try the base slug first
        if (
            not model_class.objects.filter(slug=base_slug, **filter_kwargs)
            .exclude(pk=self.pk)
            .exists()
        ):
            return base_slug
        # If not, include uuid in slug
        return f"{base_slug}-{uuid.uuid4().hex[:8]}"


class TimeStampModel(models.Model):
    """
    Abstract base model that provides automatic timestamp fields.

    Adds created_at and updated_at fields to any model that inherits from it.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class LocalizationModel(models.Model):
    """
    Abstract base model for entities with localization support.

    Provides common fields and methods for models like Section,
    Genre, Tag, and Author that need multi-language support.
    """

    name = models.CharField(
        max_length=100,
        help_text="Canonical name (default language)"
    )
    slug = models.SlugField(
        max_length=100,
        help_text="URL-friendly identifier"
    )
    description = models.TextField(
        blank=True,
        help_text="Description or details"
    )
    translations = models.JSONField(
        default=dict,
        blank=True,
        help_text="Localized names and descriptions. Format: {language_code: {name, description}}"
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not provided"""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_localized_name(self, language_code):
        """Get localized name or fall back to default"""
        if language_code in self.translations:
            return self.translations[language_code].get('name', self.name)
        return self.name

    def get_localized_description(self, language_code):
        """Get localized description or fall back to default"""
        if language_code in self.translations:
            return self.translations[language_code].get('description', self.description)
        return self.description
