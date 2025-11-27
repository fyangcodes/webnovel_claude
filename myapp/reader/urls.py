from django.urls import path, register_converter
from django.shortcuts import redirect
from django.http import HttpRequest
from . import views
from books.models import Language
from books.views import update_reading_progress


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

    # Get available language codes from database (only public for non-staff)
    user = request.user
    is_staff = user.is_authenticated and user.is_staff
    if is_staff:
        available_languages = set(Language.objects.values_list("code", flat=True))
    else:
        available_languages = set(Language.objects.filter(is_public=True).values_list("code", flat=True))

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

    # ============================================================================
    # SEO URLS
    # ============================================================================
    path("robots.txt", views.RobotsTxtView.as_view(), name="robots_txt"),

    # ============================================================================
    # GLOBAL URLS (must come before section-scoped to avoid slug conflicts)
    # ============================================================================
    # Welcome/Homepage
    path(
        "<str:language_code>/",
        views.WelcomeView.as_view(),
        name="welcome",
    ),
    # Global search (cross-section search from welcome page)
    path(
        "<str:language_code>/search/",
        views.BookSearchView.as_view(),
        name="search",
    ),
    # Global author page (for authors with books across sections)
    path(
        "<str:language_code>/author/<slug:author_slug>/",
        views.AuthorDetailView.as_view(),
        name="author_detail",
    ),

    # ============================================================================
    # SECTION-SCOPED URLS (NEW)
    # ============================================================================
    # These URLs include section in the path for better organization and SEO
    # Format: /<language>/<section>/...

    # Section home page
    path(
        "<str:language_code>/<slug:section_slug>/",
        views.SectionHomeView.as_view(),
        name="section_home",
    ),
    # Section book list
    path(
        "<str:language_code>/<slug:section_slug>/books/",
        views.SectionBookListView.as_view(),
        name="section_book_list",
    ),
    # Section genre filter (redirects to section book list with genre param)
    path(
        "<str:language_code>/<slug:section_slug>/genre/<slug:genre_slug>/",
        views.SectionGenreBookListView.as_view(),
        name="section_genre_book_list",
    ),
    # Section tag filter (redirects to section book list with tag param)
    path(
        "<str:language_code>/<slug:section_slug>/tag/<slug:tag_slug>/",
        views.SectionTagBookListView.as_view(),
        name="section_tag_book_list",
    ),
    # Section search (uses BookSearchView with section from URL path)
    path(
        "<str:language_code>/<slug:section_slug>/search/",
        views.BookSearchView.as_view(),
        name="section_search",
    ),
    # Section book detail
    path(
        "<str:language_code>/<slug:section_slug>/book/<uslug:book_slug>/",
        views.SectionBookDetailView.as_view(),
        name="section_book_detail",
    ),
    # Section chapter reading
    path(
        "<str:language_code>/<slug:section_slug>/book/<uslug:book_slug>/<uslug:chapter_slug>/",
        views.SectionChapterDetailView.as_view(),
        name="section_chapter_detail",
    ),

    # ============================================================================
    # API ENDPOINTS
    # ============================================================================

    # API endpoint for reading progress tracking
    path(
        "api/stats/reading-progress/",
        update_reading_progress,
        name="reading_progress_api",
    ),
]
