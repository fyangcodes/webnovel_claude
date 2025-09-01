from django import forms
from django.utils import timezone
from datetime import timedelta
from .models import Chapter, Book, BookMaster, ChapterMaster, TranslationJob


class BookMasterForm(forms.ModelForm):
    class Meta:
        model = BookMaster
        fields = [
            "canonical_title",
            "original_language",
        ]


class ChapterMasterForm(forms.ModelForm):
    class Meta:
        model = ChapterMaster
        fields = [
            "canonical_title",
            "bookmaster",
            "chapter_number",
        ]


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = [
            "title",
            "language",
            "description",
            "is_public",
            "progress",
        ]
        widgets = {
            "is_public": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class BookFileUploadForm(forms.Form):
    file = forms.FileField(
        help_text="Upload a text file (.txt) to extract chapters",
        widget=forms.ClearableFileInput(attrs={
            'accept': '.txt',
            'class': 'form-control'
        })
    )
    auto_create_chapters = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Automatically create ChapterMaster and Chapter objects from detected chapters in the uploaded file",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class ChapterForm(forms.ModelForm):
    class Meta:
        model = Chapter
        fields = ["title", "content", "is_public", "progress", "scheduled_at", "published_at"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 20, "cols": 80}),
            "is_public": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "scheduled_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "published_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    