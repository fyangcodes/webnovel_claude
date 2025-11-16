"""
Legacy redirect views for backward compatibility.

This module contains redirect views that maintain backward compatibility
with old URL patterns. These views redirect old URLs to new section-based URLs.

Views:
- LegacyBookDetailRedirectView: Redirects /book/<slug>/ to /<section>/book/<slug>/
- LegacyChapterDetailRedirectView: Redirects /book/<slug>/<chapter>/ to /<section>/book/<slug>/<chapter>/

These redirects will be kept indefinitely to preserve bookmarks and external links.
"""

from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import RedirectView
from django.http import Http404

from books.models import Book, Chapter


class LegacyBookDetailRedirectView(RedirectView):
    """
    Redirect legacy book detail URLs to section-based URLs.

    Converts: /<language>/book/<slug>/
    To: /<language>/<section>/book/<slug>/

    Permanent redirect (301) to help search engines and preserve SEO.
    """

    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        language_code = kwargs.get("language_code")
        book_slug = kwargs.get("book_slug")

        # Get book to determine its section
        try:
            book = Book.objects.select_related(
                "bookmaster__section", "language"
            ).get(
                slug=book_slug,
                language__code=language_code,
                is_public=True
            )
        except Book.DoesNotExist:
            raise Http404("Book not found")

        # Check if book has a section
        if not book.bookmaster.section:
            # Book has no section - cannot redirect to section URL
            # This shouldn't happen in practice if all books have sections
            raise Http404("Book has no section")

        section_slug = book.bookmaster.section.slug

        # Build new section-based URL
        return reverse(
            "reader:section_book_detail",
            args=[language_code, section_slug, book_slug]
        )


class LegacyChapterDetailRedirectView(RedirectView):
    """
    Redirect legacy chapter reading URLs to section-based URLs.

    Converts: /<language>/book/<book_slug>/<chapter_slug>/
    To: /<language>/<section>/book/<book_slug>/<chapter_slug>/

    Permanent redirect (301) to help search engines and preserve SEO.
    """

    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        language_code = kwargs.get("language_code")
        book_slug = kwargs.get("book_slug")
        chapter_slug = kwargs.get("chapter_slug")

        # Get chapter to determine the book's section
        try:
            chapter = Chapter.objects.select_related(
                "book__bookmaster__section",
                "book__language"
            ).get(
                slug=chapter_slug,
                book__slug=book_slug,
                book__language__code=language_code,
                is_public=True
            )
        except Chapter.DoesNotExist:
            raise Http404("Chapter not found")

        # Check if book has a section
        if not chapter.book.bookmaster.section:
            # Book has no section - cannot redirect to section URL
            raise Http404("Book has no section")

        section_slug = chapter.book.bookmaster.section.slug

        # Build new section-based URL
        return reverse(
            "reader:section_chapter_detail",
            args=[language_code, section_slug, book_slug, chapter_slug]
        )
