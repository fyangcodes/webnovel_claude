"""
List views for the reader app.

This module contains all list-based views:
- WelcomeView: Homepage with featured content and carousels
- BookListView: Book listing with filtering
- BookSearchView: Keyword search with weighted results
"""

from django.conf import settings
from django.views.generic import DetailView

from books.models import Book, Genre, Section, Author
from reader import cache
from .base import BaseReaderView, BaseBookListView, BaseSearchView


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


class BookSearchView(BaseSearchView):
    """
    Keyword search with optional section scoping.

    Global URL: /<language_code>/search/?q=<query>&section=<slug>&genre=<slug>...
    Section URL: /<language_code>/<section>/search/?q=<query>&genre=<slug>...

    Uses BookSearchService for weighted keyword search across sections, genres, tags,
    and entities. Supports all standard filters (section, genre, tag, status).

    When accessed via section URL, section is required from URL path.
    When accessed via global URL, section is optional from query parameter.
    """

    def get_section_for_search(self):
        """
        Get section from URL path (section-scoped) or query parameter (global).

        Priority:
        1. URL path section (/<language>/<section>/search/)
        2. Query parameter (?section=<slug>)
        """
        # Try to get section from URL path first (section-scoped URL)
        section = self.get_section()
        if section:
            return section

        # Fall back to query parameter (global URL)
        section_slug = self.request.GET.get('section')
        if section_slug:
            return Section.objects.filter(slug=section_slug).first()

        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_search_context())

        language_code = self.kwargs.get("language_code")
        section = self.get_section_for_search()

        # Check if this is a section-scoped URL (has section in URL path)
        is_section_scoped = 'section_slug' in self.kwargs

        # Context differs based on whether this is section-scoped or global
        context['show_section_nav'] = True

        if is_section_scoped and section:
            # Section-scoped: hide section badges (we're already in this section)
            context['show_section'] = False
        else:
            # Global: show section badges on book cards
            context['show_section'] = True

        # Section context
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

        context["selected_section"] = self.request.GET.get('section', '') if not is_section_scoped else ""

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


class AuthorDetailView(BaseReaderView, DetailView):
    """
    Author detail page showing author info and their books.

    URL: /<language>/author/<slug>/
    Example: /en/author/er-gen/

    Displays:
    - Author information (name, description, avatar)
    - List of ALL books by this author across all sections

    Note: Authors can write across sections (Fiction, BL, GL, etc.),
    so this view is intentionally NOT section-scoped.
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
        context["author_name"] = self.object.get_localized_name(language_code)
        context["author_description"] = self.object.get_localized_description(
            language_code
        )

        # Get author's books (published in current language, ALL sections) with optimized relations
        books = list(
            Book.objects.filter(
                bookmaster__author=self.object, language=language, is_public=True
            )
            .with_card_relations()
            .order_by("-created_at")
        )

        # Enrich books with metadata using inherited method from BaseReaderView
        context["books"] = self.enrich_books_with_metadata(books, language_code)

        return context
