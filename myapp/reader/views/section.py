"""
Section-scoped views for the reader app.

This module contains all section-scoped views that include section in the URL path.

Views:
- SectionHomeView: Section landing page with featured content
- SectionBookListView: Books filtered by section
- SectionBookDetailView: Book detail with section validation
- SectionChapterDetailView: Chapter reading with section validation
- SectionGenreBookListView: Redirect to section book list with genre filter
- SectionTagBookListView: Redirect to section book list with tag filter

Note: Section search uses BookSearchView from list_views.py (supports both global and section-scoped URLs)
"""

from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.http import Http404
from django.core.paginator import Paginator
from django.views import View
from django.views.generic import DetailView
from django.db.models import Prefetch

from books.models import Book, Chapter, Genre, Tag, BookGenre
from reader import cache
from .base import BaseBookListView, BaseBookDetailView, BaseReaderView, BaseSearchView


class SectionHomeView(BaseBookListView):
    """
    Section landing page with featured content.

    URL: /<language>/<section>/
    Example: /en/fiction/ or /zh/bl/

    Displays:
    - Section description and info
    - Featured books from this section
    - Recent updates in this section
    - Popular genres in this section
    """

    template_name = "reader/section_home.html"
    model = Book
    paginate_by = 12

    def get_queryset(self):
        """Get recent books from this section"""
        language = self.get_language()
        section = self.get_section()

        if not section:
            raise Http404("Section required")

        # Return recent public books from this section with optimized relations
        queryset = Book.objects.filter(
            language=language,
            is_public=True,
            bookmaster__section=section
        )

        return (
            queryset.with_card_relations()
            .order_by("-published_at", "-created_at")[:12]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        section = self.get_section()
        language_code = self.kwargs.get("language_code")

        # Show section nav on section home (CRITICAL - primary section navigation)
        context['show_section_nav'] = True

        # Hide section badge on book cards (we're already in this section)
        context['show_section'] = False

        # Add section to context with localized name
        context["section"] = section
        context["section_localized_name"] = section.get_localized_name(language_code)
        context["section_localized_description"] = section.get_localized_description(
            language_code
        )

        # Get genres for this section with localized names
        section_genres = cache.get_cached_genres_flat(section_id=section.id)
        context["section_genres"] = self.get_localized_genres(section_genres, language_code)

        # Featured books in this section (if configured)
        # TODO: Add FEATURED_BOOKS_BY_SECTION setting
        context["featured_books"] = []

        return context


class SectionBookListView(BaseBookListView):
    """
    Books filtered by section.

    URL: /<language>/<section>/books/?genre=<slug>&tag=<slug>&status=<status>
    Example: /en/fiction/books/?genre=fantasy&status=ongoing

    Supports additional filters:
    - ?genre=<slug> - Filter by genre
    - ?tag=<slug> - Filter by tag
    - ?status=<draft|ongoing|completed> - Filter by progress status
    """

    template_name = "reader/book_list.html"
    model = Book

    def get_queryset(self):
        language = self.get_language()
        section = self.get_section()

        if not section:
            raise Http404("Section required")

        queryset = Book.objects.filter(
            language=language,
            is_public=True,
            bookmaster__section=section
        )

        # Filter by genre if specified
        genre_slug = self.request.GET.get("genre")
        if genre_slug:
            genre = Genre.objects.filter(slug=genre_slug, section=section).first()
            if genre:
                # Get bookmaster IDs that have this genre
                bookmaster_ids = BookGenre.objects.filter(genre=genre).values_list(
                    "bookmaster_id", flat=True
                )
                queryset = queryset.filter(bookmaster_id__in=bookmaster_ids)

        # Filter by tag if specified
        tag_slug = self.request.GET.get("tag")
        if tag_slug:
            tag = Tag.objects.filter(slug=tag_slug).first()
            if tag:
                # Get bookmaster IDs that have this tag
                from books.models import BookTag
                bookmaster_ids = BookTag.objects.filter(tag=tag).values_list(
                    "bookmaster_id", flat=True
                )
                queryset = queryset.filter(bookmaster_id__in=bookmaster_ids)

        # Filter by progress/status if specified
        progress = self.request.GET.get("status")
        if progress and progress in ["draft", "ongoing", "completed"]:
            queryset = queryset.filter(progress=progress)

        # Use optimized relations for book cards
        return (
            queryset.with_card_relations()
            .order_by("-published_at", "-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        section = self.get_section()
        language_code = self.kwargs.get("language_code")

        # Show section nav on section book list (CRITICAL - only way to switch sections)
        context['show_section_nav'] = True

        # Hide section badge on book cards (we're already in this section)
        context['show_section'] = False

        # Add section to context
        context["section"] = section
        context["section_localized_name"] = section.get_localized_name(language_code)

        # Add current filter values to context
        context["selected_genre"] = self.request.GET.get("genre", "")
        context["selected_tag"] = self.request.GET.get("tag", "")
        context["selected_status"] = self.request.GET.get("status", "")

        # Get all genres for this section
        all_section_genres = cache.get_cached_genres_flat(section_id=section.id)

        # Separate primary genres with localized names
        primary_genres = []
        for g in all_section_genres:
            if g.is_primary:
                g.localized_name = g.get_localized_name(language_code)
                primary_genres.append(g)

        context["primary_genres"] = primary_genres

        # Genre hierarchy for sub-genres section
        genre_slug = self.request.GET.get("genre")
        primary_genre = None
        secondary_genres = []

        if genre_slug:
            genre = Genre.objects.select_related('section', 'parent').filter(
                slug=genre_slug, section=section
            ).first()

            if genre:
                context["current_genre"] = genre
                context["current_genre_localized_name"] = genre.get_localized_name(language_code)

                # Determine primary genre and get sub-genres
                if genre.is_primary:
                    # Primary genre selected
                    primary_genre = genre
                    primary_genre.localized_name = genre.get_localized_name(language_code)
                    primary_genre.is_active_selection = (genre_slug == genre.slug)

                    # Get all sub-genres for this primary
                    for g in all_section_genres:
                        if not g.is_primary and g.parent_id == genre.id:
                            g.localized_name = g.get_localized_name(language_code)
                            g.is_active_selection = False  # None selected yet
                            secondary_genres.append(g)
                else:
                    # Sub-genre selected
                    primary_genre = genre.parent
                    if primary_genre:
                        primary_genre.localized_name = primary_genre.get_localized_name(language_code)
                        primary_genre.is_active_selection = False  # Parent not directly selected

                        # Get all sibling sub-genres
                        for g in all_section_genres:
                            if not g.is_primary and g.parent_id == primary_genre.id:
                                g.localized_name = g.get_localized_name(language_code)
                                g.is_active_selection = (genre_slug == g.slug)
                                secondary_genres.append(g)

        context["primary_genre"] = primary_genre
        context["secondary_genres"] = secondary_genres

        # Tag context
        tag_slug = self.request.GET.get("tag")
        if tag_slug:
            tag = Tag.objects.filter(slug=tag_slug).first()
            if tag:
                context["current_tag"] = tag
                context["current_tag_localized_name"] = tag.get_localized_name(language_code)

        return context


class SectionBookDetailView(BaseBookDetailView):
    """
    Book detail with section validation.

    URL: /<language>/<section>/book/<slug>/
    Example: /en/fiction/book/reverend-insanity/

    Ensures the book belongs to the section specified in the URL.
    Returns 404 if book doesn't belong to this section.
    """

    template_name = "reader/book_detail.html"
    model = Book

    def get_queryset(self):
        """Get book queryset with section validation"""
        language = self.get_language()
        section = self.get_section()

        if not section:
            raise Http404("Section required")

        # Ensure book belongs to this section
        # Create optimized prefetch for hreflang tags (all public language versions)
        hreflang_prefetch = Prefetch(
            'bookmaster__books',
            queryset=Book.objects.filter(is_public=True).select_related('language'),
            to_attr='hreflang_books_list'
        )

        return (
            Book.objects.filter(
                language=language,
                is_public=True,
                bookmaster__section=section  # Validate section
            )
            .select_related("bookmaster", "bookmaster__section", "bookmaster__author", "language")
            .prefetch_related(
                "chapters__chaptermaster",
                "bookmaster__genres",
                "bookmaster__genres__parent",
                "bookmaster__genres__section",
                "bookmaster__tags",
                # Prefetch for hreflang tags (all public language versions)
                hreflang_prefetch,
            )
        )

    def get_context_data(self, **kwargs):
        """
        Build context data for book detail view with optimized chapter stats.

        Optimizations implemented:
        1. Single aggregation query for chapter stats (Count + Sum + Max)
           - Replaces 3 separate queries (.count() + sum() + .first())
           - Reduces chapter stats from 3 queries → 1 query

        2. Hreflang prefetch from queryset
           - Uses prefetched hreflang_books_list (to_attr pattern)
           - Eliminates 1 additional query for alternate language versions

        3. Language-aware word count calculation
           - Database-level Sum() for word_count or character_count
           - No memory overhead from loading all chapters

        Context includes:
        - chapters: Paginated chapter list (sorted by user preference)
        - total_chapters: Total published chapter count (aggregated)
        - total_words: Total word/character count (language-aware)
        - last_update: Last published chapter date (aggregated)
        - total_chapter_views: Total views across all chapters (cached)
        - author: Author object with localized name
        - hreflang_books: Alternate language versions (prefetched)
        - new_chapter_cutoff: Date cutoff for "new" badge highlighting

        Args:
            **kwargs: Additional context from parent classes

        Returns:
            dict: Template context with optimized chapter statistics
        """
        from django.utils import timezone
        from datetime import timedelta
        from django.conf import settings
        from django.db.models import Count, Sum, Max

        context = super().get_context_data(**kwargs)
        section = self.get_section()
        language_code = self.kwargs.get("language_code")

        # Show section nav on book detail (for discoverability)
        context['show_section_nav'] = True

        # Add author context with localized name
        author = self.object.bookmaster.author
        if author:
            context["author"] = author
            context["author_localized_name"] = author.get_localized_name(language_code)

        # Prefetch hreflang data (all language versions of this book)
        # Use prefetched data from queryset (hreflang_books_list) to avoid additional queries
        # This uses the Prefetch with to_attr='hreflang_books_list' from get_queryset()
        context["hreflang_books"] = self.object.bookmaster.hreflang_books_list

        # Get all published chapters with sorting
        sort_param = self.request.GET.get('sort', 'oldest')
        new_chapter_days = getattr(settings, 'NEW_CHAPTER_DAYS', 14)
        cutoff_date = timezone.now() - timedelta(days=new_chapter_days)

        # Base queryset for chapters
        all_chapters = self.object.chapters.filter(is_public=True).select_related("chaptermaster")

        if sort_param == 'latest':
            # Sort by published date, newest first
            all_chapters = all_chapters.order_by("-published_at", "-chaptermaster__chapter_number")
        elif sort_param == 'new':
            # Filter to show ONLY new chapters (within NEW_CHAPTER_DAYS)
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

        # OPTIMIZATION: Get chapter stats with a single aggregation query
        # instead of .count() + sum() + .first() which triggers 3 separate queries
        chapter_stats = self.object.chapters.filter(is_public=True).aggregate(
            total_chapters=Count('id'),
            total_words=Sum('word_count'),
            total_characters=Sum('character_count'),
            last_update=Max('published_at')
        )

        # Use aggregated stats (1 query instead of 3)
        context["total_chapters"] = chapter_stats['total_chapters'] or 0

        # Calculate total effective count based on language
        # For word-based languages use total_words, for character-based use total_characters
        if self.object.language.count_units == 'WORDS':
            context["total_words"] = chapter_stats['total_words'] or 0
        else:
            context["total_words"] = chapter_stats['total_characters'] or 0

        context["last_update"] = chapter_stats['last_update']

        # Add total chapter views from cache (already optimized)
        context["total_chapter_views"] = cache.get_cached_total_chapter_views(self.object.id)

        # Create ViewEvent immediately for tracking (before template renders)
        from books.stats import StatsService
        view_event = StatsService.track_book_view(self.object, self.request)
        context["view_event_id"] = view_event.id if view_event else None

        # Add new chapter cutoff date for highlighting new chapters
        context["new_chapter_cutoff"] = cutoff_date

        return context


class SectionChapterDetailView(BaseReaderView, DetailView):
    """
    Chapter reading with section validation.

    URL: /<language>/<section>/book/<book_slug>/<chapter_slug>/
    Example: /en/fiction/book/reverend-insanity/chapter-1/

    Ensures the book belongs to the section specified in the URL.
    Returns 404 if book doesn't belong to this section.
    """

    model = Chapter
    template_name = "reader/chapter_detail.html"
    context_object_name = "chapter"
    slug_field = "slug"
    slug_url_kwarg = "chapter_slug"

    def get_queryset(self):
        """Get chapter queryset with section and book validation"""
        language = self.get_language()
        section = self.get_section()
        book_slug = self.kwargs.get("book_slug")

        if not section:
            raise Http404("Section required")

        # Get book and validate section
        book = get_object_or_404(
            Book,
            slug=book_slug,
            language=language,
            is_public=True,
            bookmaster__section=section  # Validate section
        )

        return Chapter.objects.filter(book=book, is_public=True).select_related(
            "book__bookmaster", "book__bookmaster__section", "book__language", "chaptermaster"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        book = self.object.book
        context["book"] = book

        # HIDE section nav on chapter reading (reading immersion priority)
        context['show_section_nav'] = False

        # Add section localized name to book for template
        language_code = self.kwargs.get("language_code")
        if book.bookmaster and book.bookmaster.section:
            book.section_localized_name = book.bookmaster.section.get_localized_name(language_code)

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


class SectionGenreBookListView(View):
    """
    Redirect genre-based URLs to section book list with genre filter.

    Converts: /<language>/<section>/genre/<slug>/
    To: /<language>/<section>/books/?genre=<slug>
    """

    def get(self, request, *args, **kwargs):
        language_code = kwargs.get("language_code")
        section_slug = kwargs.get("section_slug")
        genre_slug = kwargs.get("genre_slug")

        # Build URL with query parameters
        url = reverse("reader:section_book_list", args=[language_code, section_slug])
        return redirect(f"{url}?genre={genre_slug}")


class SectionTagBookListView(View):
    """
    Redirect tag-based URLs to section book list with tag filter.

    Converts: /<language>/<section>/tag/<slug>/
    To: /<language>/<section>/books/?tag=<slug>
    """

    def get(self, request, *args, **kwargs):
        language_code = kwargs.get("language_code")
        section_slug = kwargs.get("section_slug")
        tag_slug = kwargs.get("tag_slug")

        # Build URL with query parameters
        url = reverse("reader:section_book_list", args=[language_code, section_slug])
        return redirect(f"{url}?tag={tag_slug}")
