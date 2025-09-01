from django.urls import path, register_converter
from ..views import reader_views
import re


class UnicodeSlugConverter:
    """Custom path converter for unicode slugs"""

    regex = r'[^\s/\\?%*:|"<>]+'

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


# Register the custom converter
register_converter(UnicodeSlugConverter, "uslug")

app_name = "books_reader"

urlpatterns = [
    path(
        "<str:language_code>/",
        reader_views.BookListView.as_view(),
        name="book_list",
    ),
    path(
        "<str:language_code>/<uslug:book_slug>/",
        reader_views.BookDetailView.as_view(),
        name="book_detail",
    ),
    path(
        "<str:language_code>/<uslug:book_slug>/<uslug:chapter_slug>/",
        reader_views.ChapterDetailView.as_view(),
        name="chapter_detail",
    ),
]
