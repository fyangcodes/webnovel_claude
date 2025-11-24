"""
Detail views for the reader app.

This module contains all detail views:
- BookDetailView: Book detail page with chapters and taxonomy
- ChapterDetailView: Chapter reading page with navigation
"""

from django.shortcuts import get_object_or_404
from django.views.generic import DetailView
from django.core.paginator import Paginator

from books.models import Book, Chapter, Author
from reader import cache
from .base import BaseReaderView, BaseBookDetailView


class BookDetailView(BaseBookDetailView):
    """
    Reader-friendly book detail page with chapter list and taxonomy.

    Displays:
    - Book information (title, author, description, cover)
    - Taxonomy (section, genres, tags)
    - Chapter list with pagination (20 per page)
    - Reading statistics (views, chapters, words)
    """

    template_name = "reader/book_detail.html"
    model = Book

    def get_queryset(self):
        """Get book queryset with language validation"""
        language = self.get_language()

        return (
            Book.objects.filter(language=language, is_public=True)
            .select_related("bookmaster", "bookmaster__section", "bookmaster__author", "language")
            .prefetch_related(
                "chapters__chaptermaster",
                "bookmaster__genres",
                "bookmaster__genres__parent",
                "bookmaster__genres__section",
                "bookmaster__tags"
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")

        # Add author context with localized name
        author = self.object.bookmaster.author
        if author:
            context["author"] = author
            context["author_localized_name"] = author.get_localized_name(language_code)

        # Get all published chapters with sorting
        sort_param = self.request.GET.get('sort', 'oldest')

        all_chapters = self.object.chapters.filter(is_public=True).select_related("chaptermaster")

        if sort_param == 'latest':
            # Sort by published date, newest first
            all_chapters = all_chapters.order_by("-published_at", "-chaptermaster__chapter_number")
        elif sort_param == 'new':
            # Filter to show ONLY new chapters (within NEW_CHAPTER_DAYS)
            from django.utils import timezone
            from datetime import timedelta
            from django.conf import settings

            new_chapter_days = getattr(settings, 'NEW_CHAPTER_DAYS', 14)
            cutoff_date = timezone.now() - timedelta(days=new_chapter_days)

            all_chapters = all_chapters.filter(
                published_at__gte=cutoff_date
            ).order_by("-published_at", "chaptermaster__chapter_number")
        else:  # oldest (default)
            all_chapters = all_chapters.order_by("chaptermaster__chapter_number")

        # Pagination for chapters
        paginator = Paginator(all_chapters, 20)  # 20 chapters per page
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context["chapters"] = page_obj
        context["is_paginated"] = page_obj.has_other_pages()
        context["page_obj"] = page_obj

        # Reading progress context (use all chapters for stats, not just current page)
        context["total_chapters"] = all_chapters.count()
        context["total_words"] = sum(
            chapter.effective_count for chapter in all_chapters
        )

        # Last update from most recently published chapter
        latest_chapter = all_chapters.order_by("-published_at").first()
        context["last_update"] = latest_chapter.published_at if latest_chapter else None

        # Add total chapter views from cache
        context["total_chapter_views"] = cache.get_cached_total_chapter_views(self.object.id)

        # Create ViewEvent immediately for tracking (before template renders)
        from books.stats import StatsService
        view_event = StatsService.track_book_view(self.object, self.request)
        context["view_event_id"] = view_event.id if view_event else None

        # Add new chapter cutoff date for highlighting new chapters
        from django.utils import timezone
        from datetime import timedelta
        from django.conf import settings
        new_chapter_days = getattr(settings, 'NEW_CHAPTER_DAYS', 14)
        context["new_chapter_cutoff"] = timezone.now() - timedelta(days=new_chapter_days)

        return context


class ChapterDetailView(BaseReaderView, DetailView):
    """
    Reader-friendly chapter reading page.

    Displays:
    - Chapter content
    - Navigation (previous/next chapter)
    - Reading progress (chapter X of Y)
    - Language switcher
    """

    model = Chapter
    template_name = "reader/chapter_detail.html"
    context_object_name = "chapter"
    slug_field = "slug"
    slug_url_kwarg = "chapter_slug"

    def get_queryset(self):
        """Get chapter queryset with book and language validation"""
        language = self.get_language()
        book_slug = self.kwargs.get("book_slug")

        # Get book with language validation
        book = get_object_or_404(
            Book, slug=book_slug, language=language, is_public=True
        )

        return Chapter.objects.filter(book=book, is_public=True).select_related(
            "book__bookmaster", "book__language", "chaptermaster"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["book"] = self.object.book

        # Get cached navigation data (eliminates 4 queries: previous, next, position, total)
        current_chapter_number = self.object.chaptermaster.chapter_number
        nav_data = cache.get_cached_chapter_navigation(
            self.object.book.id,
            current_chapter_number
        )

        # Convert cached navigation data to Chapter objects for template compatibility
        if nav_data['previous']:
            context["previous_chapter"] = Chapter.objects.filter(
                id=nav_data['previous']['id']
            ).first()
        else:
            context["previous_chapter"] = None

        if nav_data['next']:
            context["next_chapter"] = Chapter.objects.filter(
                id=nav_data['next']['id']
            ).first()
        else:
            context["next_chapter"] = None

        context["chapter_position"] = nav_data['position']
        context["total_chapters"] = nav_data['total']

        # Create ViewEvent immediately for tracking (before template renders)
        from books.stats import StatsService
        view_event = StatsService.track_chapter_view(self.object, self.request)
        context["view_event_id"] = view_event.id if view_event else None

        return context


class AuthorDetailView(BaseReaderView, DetailView):
    """
    Author detail page showing author info and their books.

    URL: /<language>/author/<slug>/
    Example: /en/author/er-gen/

    Displays:
    - Author information (name, description, avatar)
    - List of books by this author
    """

    template_name = "reader/author_detail.html"
    model = Author
    context_object_name = "author"
    slug_field = "slug"
    slug_url_kwarg = "author_slug"

    def get_object(self, queryset=None):
        """Use cached author lookup by slug."""
        from django.http import Http404
        slug = self.kwargs.get(self.slug_url_kwarg)
        author = cache.get_cached_author_by_slug(slug)
        if author is None:
            raise Http404("Author not found")
        return author

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language = self.get_language()
        language_code = language.code

        # Localized author info
        context['author_name'] = self.object.get_localized_name(language_code)
        context['author_description'] = self.object.get_localized_description(language_code)

        # Get author's books (published in current language)
        books = list(Book.objects.filter(
            bookmaster__author=self.object,
            language=language,
            is_public=True
        ).select_related(
            'bookmaster', 'bookmaster__section', 'language'
        ).prefetch_related(
            'bookmaster__genres', 'bookmaster__genres__section'
        ).order_by('-created_at'))

        # Enrich books with metadata using inherited method from BaseReaderView
        context['books'] = self.enrich_books_with_metadata(books, language_code)

        return context
