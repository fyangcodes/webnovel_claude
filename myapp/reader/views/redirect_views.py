"""
Redirect views for the reader app.

This module contains redirect views for URL routing:
- GenreBookListView: Redirects genre URLs to query-based filtering
- TagBookListView: Redirects tag URLs to query-based filtering
"""

from django.shortcuts import redirect
from django.urls import reverse
from django.views import View


class GenreBookListView(View):
    """
    Redirect genre-based URLs to query parameter filtering.

    Converts: /<language>/genre/<slug>/
    To: /<language>/books/?genre=<slug>
    """

    def get(self, request, *args, **kwargs):
        language_code = kwargs.get("language_code")
        genre_slug = kwargs.get("genre_slug")

        # Build URL with query parameters
        url = reverse("reader:book_list", args=[language_code])
        return redirect(f"{url}?genre={genre_slug}")


class TagBookListView(View):
    """
    Redirect tag-based URLs to query parameter filtering.

    Converts: /<language>/tag/<slug>/
    To: /<language>/books/?tag=<slug>
    """

    def get(self, request, *args, **kwargs):
        language_code = kwargs.get("language_code")
        tag_slug = kwargs.get("tag_slug")

        # Build URL with query parameters
        url = reverse("reader:book_list", args=[language_code])
        return redirect(f"{url}?tag={tag_slug}")
