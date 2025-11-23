"""
List views for the reader app.

This module contains all list-based views:
- WelcomeView: Homepage with featured content and carousels
- BookListView: Book listing with filtering
- BookSearchView: Keyword search with weighted results
"""

from django.conf import settings

from books.models import Book, Genre, Section, Tag, BookGenre
from reader import cache
from .base import BaseBookListView, BaseSearchView


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


class BookSearchView(BaseSearchView):
    """
    Global keyword search across all sections.

    URL: /<language_code>/search/?q=<query>&section=<slug>&genre=<slug>...

    Uses BookSearchService for weighted keyword search across sections, genres, tags,
    and entities. Supports all standard filters (section, genre, tag, status).
    """

    def get_section_for_search(self):
        """Get section from query parameter (optional filter)."""
        section_slug = self.request.GET.get('section')
        if section_slug:
            return Section.objects.filter(slug=section_slug).first()
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_search_context())

        language_code = self.kwargs.get("language_code")

        # Global search specific context
        context['show_section_nav'] = True
        context['show_section'] = True  # Show section badges on book cards

        # Section filter
        section_slug = self.request.GET.get('section')
        if section_slug:
            section = Section.objects.filter(slug=section_slug).first()
            if section:
                context["section"] = section
                context["section_localized_name"] = section.get_localized_name(language_code)
                # Add genre hierarchy for this section
                self._add_genre_hierarchy_context(context, section, language_code)
        else:
            # No section filter - show all primary genres from all sections
            all_genres = cache.get_cached_genres_flat()
            primary_genres = []
            for g in all_genres:
                if g.is_primary:
                    g.localized_name = g.get_localized_name(language_code)
                    if g.section:
                        g.section_localized_name = g.section.get_localized_name(language_code)
                    primary_genres.append(g)
            context["primary_genres"] = primary_genres

        context["selected_section"] = section_slug or ""

        return context

    def _add_genre_hierarchy_context(self, context, section, language_code):
        """Add full genre hierarchy for section-filtered search."""
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
