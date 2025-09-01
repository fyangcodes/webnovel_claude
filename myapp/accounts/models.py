from django.contrib.auth.models import AbstractUser
from django.db import models

from .choices import Role


class User(AbstractUser):
    """Simplified user model with just 3 essential roles"""

    # Essential fields only
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.READER,
        help_text="User role in the translation system",
    )

    # Optional profile fields
    pen_name = models.CharField(
        max_length=100, blank=True, help_text="Display name for translations"
    )

    class Meta:
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["is_active", "role"]),
        ]

    def __str__(self):
        if self.role != Role.READER:
            return f"{self.display_name} ({self.role})"
        return f"{self.display_name}"

    @property
    def display_name(self):
        """Return pen_name if available, otherwise username"""
        return self.pen_name if self.pen_name else self.username
