"""
List views for the reader app.

This module contains all list-based views:
- WelcomeView: Homepage with featured content and carousels
- BookListView: Book listing with filtering
- BookSearchView: Keyword search with weighted results
"""

from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db.models import Case, When

from books.models import Book, Genre, Section, Tag, BookGenre
from books.utils.search import BookSearchService
from reader import cache
from .base import BaseBookListView


class WelcomeView(BaseBookListView):
    """
    Welcome/Homepage with carousels and featured content.

    Now inherits from BaseBookListView to eliminate code duplication.
    Provides featured books, recently updated, and new arrivals.
    """

    template_name = "reader/welcome.html"
    model = Book

    def get_queryset(self):
        """
        Return empty queryset - this view doesn't use standard pagination.

        Instead, it provides separate sections for featured, recent, and new books.
        """
        return Book.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")

        # Show section nav on welcome page (primary cross-section navigation)
        context['show_section_nav'] = True

        # Get featured genres from settings grouped by section
        featured_genre_ids = getattr(settings, "FEATURED_GENRES", [])
        if featured_genre_ids:
            featured_genres = cache.get_cached_featured_genres(featured_genre_ids)
            # Add localized names
            for genre in featured_genres:
                genre.localized_name = genre.get_localized_name(language_code)
                if genre.section:
                    genre.section_localized_name = genre.section.get_localized_name(language_code)
                if genre.parent:
                    genre.parent_localized_name = genre.parent.get_localized_name(language_code)

            # Group featured genres by section
            featured_by_section = {}
            for genre in featured_genres:
                section_id = genre.section.id if genre.section else None
                if section_id not in featured_by_section:
                    featured_by_section[section_id] = {
                        'section': genre.section,
                        'genres': []
                    }
                featured_by_section[section_id]['genres'].append(genre)

            context["featured_genres"] = featured_genres  # Flat list for compatibility
            context["featured_genres_by_section"] = featured_by_section  # NEW: Grouped by section
        else:
            context["featured_genres"] = []
            context["featured_genres_by_section"] = {}

        # Get featured books from settings (cached, eliminates complex query)
        featured_bookmaster_ids = getattr(settings, "FEATURED_BOOKS", [])
        if featured_bookmaster_ids:
            featured_books = cache.get_cached_featured_books(
                language_code, featured_bookmaster_ids
            )
            context["featured_books"] = self.enrich_books_with_metadata(featured_books, language_code)
        else:
            context["featured_books"] = []

        # Recently updated books - cached (eliminates annotated query + N+1)
        recently_updated = cache.get_cached_recently_updated(language_code, limit=6)
        context["recently_updated"] = self.enrich_books_with_metadata(
            recently_updated, language_code
        )

        # New arrivals - cached (eliminates query + N+1)
        new_arrivals = cache.get_cached_new_arrivals(language_code, limit=6)
        context["new_arrivals"] = self.enrich_books_with_metadata(new_arrivals, language_code)

        return context


class BookListView(BaseBookListView):
    """
    Reader-friendly book listing page with section/genre/tag filtering.

    Supports query parameter filtering:
    - ?section=<slug> - Filter by section
    - ?genre=<slug> - Filter by genre
    - ?tag=<slug> - Filter by tag
    - ?status=<draft|ongoing|completed> - Filter by progress status

    Provides breadcrumb navigation based on active filters.
    """

    template_name = "reader/book_list.html"
    model = Book

    def get_queryset(self):
        language = self.get_language()
        queryset = Book.objects.filter(language=language, is_public=True)

        # Filter by section if specified
        section_slug = self.request.GET.get("section")
        if section_slug:
            section = Section.objects.filter(slug=section_slug).first()
            if section:
                queryset = queryset.filter(bookmaster__section=section)

        # Filter by genre if specified
        genre_slug = self.request.GET.get("genre")
        if genre_slug:
            genre = Genre.objects.filter(slug=genre_slug).first()
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
        language_code = self.kwargs.get("language_code")

        # Add current filter values to context
        context["selected_section"] = self.request.GET.get("section", "")
        context["selected_genre"] = self.request.GET.get("genre", "")
        context["selected_tag"] = self.request.GET.get("tag", "")
        context["selected_status"] = self.request.GET.get("status", "")

        # Add breadcrumb data
        breadcrumbs = []

        # Section breadcrumb
        section_slug = self.request.GET.get("section")
        if section_slug:
            section = Section.objects.filter(slug=section_slug).first()
            if section:
                context["current_section"] = section
                context["current_section_localized_name"] = section.get_localized_name(language_code)
                breadcrumbs.append({
                    'type': 'section',
                    'name': section.get_localized_name(language_code),
                    'slug': section.slug,
                    'url': f"?section={section.slug}"
                })

        # Genre breadcrumb
        genre_slug = self.request.GET.get("genre")
        if genre_slug:
            genre = Genre.objects.select_related('section', 'parent').filter(slug=genre_slug).first()
            if genre:
                context["current_genre"] = genre
                context["current_genre_localized_name"] = genre.get_localized_name(language_code)

                # Build genre breadcrumb with hierarchy
                genre_crumb = {
                    'type': 'genre',
                    'name': genre.get_localized_name(language_code),
                    'slug': genre.slug,
                    'url': f"?genre={genre.slug}"
                }

                # Add section if genre has section
                if genre.section and not section_slug:
                    breadcrumbs.append({
                        'type': 'section',
                        'name': genre.section.get_localized_name(language_code),
                        'slug': genre.section.slug,
                        'url': f"?section={genre.section.slug}"
                    })

                # Add parent genre if exists
                if genre.parent:
                    breadcrumbs.append({
                        'type': 'genre',
                        'name': genre.parent.get_localized_name(language_code),
                        'slug': genre.parent.slug,
                        'url': f"?genre={genre.parent.slug}",
                        'is_parent': True
                    })

                breadcrumbs.append(genre_crumb)

        # Tag breadcrumb
        tag_slug = self.request.GET.get("tag")
        if tag_slug:
            tag = Tag.objects.filter(slug=tag_slug).first()
            if tag:
                context["current_tag"] = tag
                context["current_tag_localized_name"] = tag.get_localized_name(language_code)
                breadcrumbs.append({
                    'type': 'tag',
                    'name': tag.get_localized_name(language_code),
                    'slug': tag.slug,
                    'url': f"?tag={tag.slug}",
                    'category': tag.get_category_display()
                })

        context["breadcrumbs"] = breadcrumbs

        return context


class BookSearchView(BaseBookListView):
    """
    Keyword search view with filtering.

    URL: /<language_code>/search/?q=<query>&section=<slug>&genre=<slug>...

    Uses BookSearchService for weighted keyword search across sections, genres, tags,
    and entities. Supports all standard filters (section, genre, tag, status).
    """
    template_name = "reader/search.html"
    model = Book
    paginate_by = 20

    def get_queryset(self):
        """
        Get search results using BookSearchService.

        Returns empty queryset if no query provided.
        """
        query = self.request.GET.get('q', '').strip()

        if not query:
            # No query - return empty queryset
            self.search_results = None
            return Book.objects.none()

        # Get filter parameters
        section_slug = self.request.GET.get('section')
        genre_slug = self.request.GET.get('genre')
        tag_slug = self.request.GET.get('tag')
        status = self.request.GET.get('status')

        # Get language
        language = self.get_language()

        # Perform search (returns all results, pagination handled by Django)
        search_results = BookSearchService.search(
            query=query,
            language_code=language.code,
            section_slug=section_slug,
            genre_slug=genre_slug,
            tag_slug=tag_slug,
            status=status,
            limit=500  # Large limit, let Django paginate
        )

        # Store search metadata for context
        self.search_results = search_results

        # Return books as list (Django will paginate)
        # We need to convert to queryset for proper pagination
        book_ids = [book.id for book in search_results['books']]

        if not book_ids:
            return Book.objects.none()

        # Return queryset maintaining search order
        queryset = Book.objects.filter(id__in=book_ids).select_related(
            "bookmaster", "bookmaster__section", "language"
        ).prefetch_related(
            "chapters", "bookmaster__genres", "bookmaster__genres__section", "bookmaster__tags"
        )

        # Preserve search ranking order
        preserved_order = Case(*[When(id=pk, then=pos) for pos, pk in enumerate(book_ids)])
        queryset = queryset.order_by(preserved_order)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add search query to context
        context['search_query'] = self.request.GET.get('q', '').strip()

        # Add search metadata if available
        if self.search_results:
            context['matched_keywords'] = self.search_results['matched_keywords']
            context['search_time_ms'] = self.search_results['search_time_ms']
            context['total_results'] = self.search_results['total_results']
        else:
            context['matched_keywords'] = []
            context['search_time_ms'] = 0
            context['total_results'] = 0

        # Add current filter values to context (for filter UI)
        context["selected_section"] = self.request.GET.get("section", "")
        context["selected_genre"] = self.request.GET.get("genre", "")
        context["selected_tag"] = self.request.GET.get("tag", "")
        context["selected_status"] = self.request.GET.get("status", "")

        return context
