"""
Section-scoped views for the reader app.

This module contains all section-scoped views that include section in the URL path.

Views:
- SectionHomeView: Section landing page with featured content
- SectionBookListView: Books filtered by section
- SectionBookDetailView: Book detail with section validation
- SectionChapterDetailView: Chapter reading with section validation
- SectionSearchView: Search within a section
- SectionGenreBookListView: Redirect to section book list with genre filter
- SectionTagBookListView: Redirect to section book list with tag filter
"""

from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.http import Http404
from django.core.paginator import Paginator
from django.views import View
from django.views.generic import DetailView

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

        # Return recent public books from this section
        queryset = Book.objects.filter(
            language=language,
            is_public=True,
            bookmaster__section=section
        )

        return (
            queryset.select_related("bookmaster", "bookmaster__section", "language")
            .prefetch_related("chapters", "bookmaster__genres", "bookmaster__genres__section", "bookmaster__tags")
            .order_by("-published_at", "-created_at")[:12]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        section = self.get_section()
        language_code = self.kwargs.get("language_code")

        # Show section nav on section home (CRITICAL - primary section navigation)
        context['show_section_nav'] = True

        # Add section to context with localized name
        context["section"] = section
        context["section_localized_name"] = section.get_localized_name(language_code)

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

        return (
            queryset.select_related("bookmaster", "bookmaster__section", "language")
            .prefetch_related("chapters", "bookmaster__genres", "bookmaster__genres__section", "bookmaster__tags")
            .order_by("-published_at", "-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        section = self.get_section()
        language_code = self.kwargs.get("language_code")

        # Show section nav on section book list (CRITICAL - only way to switch sections)
        context['show_section_nav'] = True

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
        return (
            Book.objects.filter(
                language=language,
                is_public=True,
                bookmaster__section=section  # Validate section
            )
            .select_related("bookmaster", "bookmaster__section", "language")
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
        section = self.get_section()

        # Show section nav on book detail (for discoverability)
        context['show_section_nav'] = True

        # Get all published chapters
        all_chapters = (
            self.object.chapters.filter(is_public=True)
            .select_related("chaptermaster")
            .order_by("chaptermaster__chapter_number")
        )

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


class SectionSearchView(BaseSearchView):
    """
    Search within a specific section.

    URL: /<language>/<section>/search/?q=<query>&genre=<slug>&tag=<slug>...
    Example: /en/fiction/search/?q=cultivation&genre=fantasy

    Scoped to a specific section from URL path.
    """

    def get_section_for_search(self):
        """Get section from URL path (required)."""
        section = self.get_section()
        if not section:
            raise Http404("Section required")
        return section

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_search_context())

        section = self.get_section_for_search()
        language_code = self.kwargs.get("language_code")

        # Section-scoped specific context
        context['show_section_nav'] = True
        context["section"] = section
        context["section_localized_name"] = section.get_localized_name(language_code)

        # Add genre hierarchy context
        self._add_genre_hierarchy_context(context, section, language_code)

        return context

    def _add_genre_hierarchy_context(self, context, section, language_code):
        """Add full genre hierarchy for section-scoped search."""
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
