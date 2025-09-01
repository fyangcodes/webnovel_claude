from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from .models import User

# Removed collaboration imports for simplified MVP

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    """Simplified form for creating new users"""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "role", "pen_name")


class CustomUserChangeForm(UserChangeForm):
    """Simplified form for editing user profiles"""

    class Meta(UserChangeForm.Meta):
        model = User
        fields = ("username", "email", "role", "pen_name")