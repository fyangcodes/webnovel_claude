from django.contrib import admin
from reader.models import StyleConfig


@admin.register(StyleConfig)
class StyleConfigAdmin(admin.ModelAdmin):
    """Admin interface for StyleConfig model."""

    list_display = ['id', 'content_type', 'object_id', 'content_object', 'color', 'icon', 'created_at']
    list_filter = ['content_type', 'created_at']
    search_fields = ['color', 'icon', 'object_id']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Object Reference', {
            'fields': ('content_type', 'object_id')
        }),
        ('Visual Styling', {
            'fields': ('color', 'icon', 'custom_styles')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def content_object(self, obj):
        """Display the linked object."""
        return str(obj.content_object) if obj.content_object else '-'
    content_object.short_description = 'Styled Object'
