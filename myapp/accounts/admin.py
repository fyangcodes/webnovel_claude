from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "role",
        "pen_name",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "email", "pen_name")
    ordering = ("-date_joined",)

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Custom Fields", {"fields": ("role", "pen_name")}),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Custom Fields", {"fields": ("role", "pen_name")}),
    )
