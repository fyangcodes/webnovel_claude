from django.urls import path, register_converter
from django.shortcuts import redirect
from django.http import HttpRequest
from . import views
from books.models import Language


class UnicodeSlugConverter:
    """Custom path converter for unicode slugs"""

    regex = r'[^\s/\\?%*:|"<>]+'

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


# Register the custom converter
register_converter(UnicodeSlugConverter, "uslug")


def language_redirect(request: HttpRequest):
    """Redirect to user's preferred language or fallback to English"""
    # Get browser's preferred languages
    accept_language = request.META.get("HTTP_ACCEPT_LANGUAGE", "")

    # Parse accept-language header to get preferred languages
    preferred_languages = []
    if accept_language:
        for lang_item in accept_language.split(","):
            lang_code = lang_item.split(";")[0].strip().lower()
            preferred_languages.append(lang_code)

    # Get available language codes from database
    available_languages = set(Language.objects.values_list("code", flat=True))

    # Try to find a match with browser languages
    for lang_code in preferred_languages:
        # Check exact match first
        if lang_code in available_languages:
            return redirect(f"/{lang_code}/")

        # Check primary language (e.g., 'zh' from 'zh-CN')
        primary_lang = lang_code.split("-")[0]

        # Find any language that starts with the primary language
        for available_lang in available_languages:
            if available_lang.lower().startswith(primary_lang):
                return redirect(f"/{available_lang}/")

    # Fallback to English if available, otherwise first available language
    if "en" in available_languages:
        return redirect("/en/")
    elif available_languages:
        first_lang = sorted(available_languages)[0]
        return redirect(f"/{first_lang}/")
    else:
        # If no languages configured, fallback to 'en'
        return redirect("/en/")


app_name = "reader"

urlpatterns = [
    path("", language_redirect, name="language_redirect"),
    # Example view for Tailwind base template
    path(
        "<str:language_code>/example/",
        views.TailwindExampleView.as_view(),
        name="tailwind_example",
    ),
    # Welcome/Homepage
    path(
        "<str:language_code>/",
        views.WelcomeView.as_view(),
        name="welcome",
    ),
    # Genre overview page
    path(
        "<str:language_code>/genres/",
        views.GenreListView.as_view(),
        name="genre_list",
    ),
    # Specific genre's books
    path(
        "<str:language_code>/genre/<slug:genre_slug>/",
        views.GenreBookListView.as_view(),
        name="genre_book_list",
    ),
    # All books page
    path(
        "<str:language_code>/books/",
        views.BookListView.as_view(),
        name="book_list",
    ),
    # Book detail page
    path(
        "<str:language_code>/book/<uslug:book_slug>/",
        views.BookDetailView.as_view(),
        name="book_detail",
    ),
    # Chapter reading page
    path(
        "<str:language_code>/book/<uslug:book_slug>/<uslug:chapter_slug>/",
        views.ChapterDetailView.as_view(),
        name="chapter_detail",
    ),
]
