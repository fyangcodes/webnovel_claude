"""
Base view classes for the reader app.

This module contains:
- BaseReaderView: Universal base for all reader views with language/section validation
- BaseBookListView: Base for list views with book enrichment and pagination
- BaseBookDetailView: Base for book detail views with localization
"""

from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView
from django.http import Http404

from books.models import Language, Section
from reader import cache


class BaseReaderView:
    """
    Universal base class for all reader views.

    Provides:
    - Language validation and retrieval
    - Section validation and retrieval (optional)
    - Global navigation context (languages, sections, genres, tags)
    - Localization helpers for all taxonomy entities
    """

    def get_language(self):
        """
        Get language from URL kwargs and check visibility permissions.

        Non-staff users can only access public languages.
        Staff users can access all languages (including private ones).

        Returns:
            Language: The validated language object

        Raises:
            Http404: If language doesn't exist or user doesn't have permission
        """
        language_code = self.kwargs.get("language_code")
        language = get_object_or_404(Language, code=language_code)

        # Check if user can access this language
        user = self.request.user
        is_staff = user.is_authenticated and user.is_staff

        if not language.is_public and not is_staff:
            # Non-staff users cannot access private languages
            raise Http404("Language not found")

        return language

    def get_section(self):
        """
        Get section from URL kwargs and validate.

        Returns None if no section in URL (for views that don't require section).

        Returns:
            Section or None: The validated section object or None

        Raises:
            Http404: If section doesn't exist
        """
        section_slug = self.kwargs.get("section_slug")
        if not section_slug:
            return None

        section = get_object_or_404(Section, slug=section_slug)

        # TODO: Add permission checks if needed
        # e.g., if section.is_mature and not user.is_authenticated:
        #     raise PermissionDenied("Must be logged in to view mature content")

        return section

    def get_localized_genres(self, genres, language_code):
        """
        Add localized names to genre objects.

        Also adds parent genre localized name if genre has a parent,
        and section localized name if genre has a section.

        Args:
            genres: Queryset or list of Genre objects
            language_code: Language code for localization

        Returns:
            List of genres with localized names attached
        """
        for genre in genres:
            genre.localized_name = genre.get_localized_name(language_code)
            if genre.parent:
                genre.parent_localized_name = genre.parent.get_localized_name(language_code)
            if genre.section:
                genre.section_localized_name = genre.section.get_localized_name(language_code)
        return genres

    def get_localized_sections(self, sections, language_code):
        """
        Add localized names to section objects.

        Args:
            sections: Queryset or list of Section objects
            language_code: Language code for localization

        Returns:
            List of sections with localized names attached
        """
        for section in sections:
            section.localized_name = section.get_localized_name(language_code)
        return sections

    def get_localized_tags(self, tags, language_code):
        """
        Add localized names to tag objects.

        Args:
            tags: Queryset or list of Tag objects
            language_code: Language code for localization

        Returns:
            List of tags with localized names attached
        """
        for tag in tags:
            tag.localized_name = tag.get_localized_name(language_code)
        return tags

    def localize_hierarchical_genres(self, genres_hierarchical, language_code):
        """
        Add localized names to hierarchical genre structure.

        Modifies the genres_hierarchical dict in-place to add localized names
        to all sections, primary genres, and sub-genres.

        Args:
            genres_hierarchical: Dict from cache.get_cached_genres()
            language_code: Language code for localization

        Returns:
            The modified genres_hierarchical dict
        """
        for section_id, section_data in genres_hierarchical.items():
            # Localize section name
            if section_data['section']:
                section_data['section'].localized_name = section_data['section'].get_localized_name(language_code)

            # Localize primary genres
            for genre in section_data['primary_genres']:
                genre.localized_name = genre.get_localized_name(language_code)
                genre.section_localized_name = genre.section.get_localized_name(language_code)

            # Localize sub-genres
            for parent_id, sub_genres in section_data['sub_genres'].items():
                for genre in sub_genres:
                    genre.localized_name = genre.get_localized_name(language_code)
                    if genre.parent:
                        genre.parent_localized_name = genre.parent.get_localized_name(language_code)
                    genre.section_localized_name = genre.section.get_localized_name(language_code)

        return genres_hierarchical

    def get_context_data(self, **kwargs):
        """
        Add global navigation context to all reader views.

        Provides:
        - current_language: Current language object
        - languages: All accessible languages (cached)
        - sections: All sections with localized names (cached)
        - genres_hierarchical: Hierarchical genre structure (cached)
        - genres: Flat genre list for backward compatibility (cached)
        - tags_by_category: Tags grouped by category (cached)
        """
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")

        # Current language
        context["current_language"] = self.get_language()

        # Use cached languages (eliminates 1 query per request)
        # Staff sees all languages, readers see only public languages
        context["languages"] = cache.get_cached_languages(user=self.request.user)

        # Add sections with localized names (cached)
        sections = cache.get_cached_sections(user=self.request.user)
        context["sections"] = self.get_localized_sections(sections, language_code)

        # Use hierarchical genre structure grouped by section (cached)
        genres_hierarchical = cache.get_cached_genres()
        context["genres_hierarchical"] = self.localize_hierarchical_genres(
            genres_hierarchical, language_code
        )

        # Also provide flat genre list for backward compatibility
        genres_flat = cache.get_cached_genres_flat()
        context["genres"] = self.get_localized_genres(genres_flat, language_code)

        # Add tags grouped by category (cached)
        tags_by_category = cache.get_cached_tags()
        # Add localized names to tags
        for category, tags in tags_by_category.items():
            for tag in tags:
                tag.localized_name = tag.get_localized_name(language_code)
        context["tags_by_category"] = tags_by_category

        return context


class BaseBookListView(BaseReaderView, ListView):
    """
    Base view for book list pages.

    Provides:
    - Book queryset with proper filtering
    - Book enrichment (chapter counts, views, localized taxonomy)
    - Pagination (12 books per page)
    - All BaseReaderView functionality
    """

    model = None  # Will be set to Book in subclasses
    context_object_name = "books"
    paginate_by = 12

    def enrich_books_with_metadata(self, books, language_code):
        """
        Add published chapters count, total views, localized genres, and section to books.

        Uses cached data to eliminate N+1 queries.

        Args:
            books: Queryset or list of Book objects
            language_code: Language code for localization

        Returns:
            List of enriched book objects
        """
        enriched_books = []
        for book in books:
            # Use cached chapter count (eliminates N+1 query)
            book.published_chapters_count = cache.get_cached_chapter_count(book.id)

            # Add total chapter views (eliminates N+1 query)
            book.total_chapter_views = cache.get_cached_total_chapter_views(book.id)

            # Add localized section name if section exists
            if hasattr(book.bookmaster, 'section') and book.bookmaster.section:
                book.section_localized_name = book.bookmaster.section.get_localized_name(language_code)
            else:
                book.section_localized_name = None

            # Add localized names to each genre (including parent)
            for genre in book.bookmaster.genres.all():
                genre.localized_name = genre.get_localized_name(language_code)
                if genre.parent:
                    genre.parent_localized_name = genre.parent.get_localized_name(language_code)
                # Add section localized name if genre has section
                if genre.section:
                    genre.section_localized_name = genre.section.get_localized_name(language_code)

            enriched_books.append(book)

        return enriched_books

    def get_context_data(self, **kwargs):
        """Add enriched books to context"""
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")

        # Enrich books with metadata (using cached chapter counts)
        context["books"] = self.enrich_books_with_metadata(
            context["books"], language_code
        )

        return context


class BaseBookDetailView(BaseReaderView, DetailView):
    """
    Base view for book detail pages.

    Provides:
    - Book queryset with proper select_related/prefetch_related
    - Book localization (section, genres, tags)
    - All BaseReaderView functionality
    """

    model = None  # Will be set to Book in subclasses
    context_object_name = "book"
    slug_field = "slug"
    slug_url_kwarg = "book_slug"

    def get_context_data(self, **kwargs):
        """
        Add localized book taxonomy to context.

        Localizes:
        - Section name
        - Genre names (with parent hierarchy)
        - Tag names (grouped by category)
        """
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")

        # Add localized section name to book object and context
        if self.object.bookmaster.section:
            self.object.section_localized_name = self.object.bookmaster.section.get_localized_name(language_code)
            context["section_localized_name"] = self.object.section_localized_name
            context["section"] = self.object.bookmaster.section

        # Add localized genre names with hierarchy
        genres = self.object.bookmaster.genres.all()
        for genre in genres:
            genre.localized_name = genre.get_localized_name(language_code)
            if genre.parent:
                genre.parent_localized_name = genre.parent.get_localized_name(language_code)
            if genre.section:
                genre.section_localized_name = genre.section.get_localized_name(language_code)
        context["genres"] = genres

        # Set primary genre on book object for breadcrumb (first genre without parent)
        primary_genres = [g for g in genres if not g.parent]
        self.object.primary_genre = primary_genres[0] if primary_genres else None

        # Add localized tag names grouped by category
        tags = self.object.bookmaster.tags.all()
        tags_by_category = {}
        for tag in tags:
            tag.localized_name = tag.get_localized_name(language_code)
            category = tag.category
            if category not in tags_by_category:
                tags_by_category[category] = []
            tags_by_category[category].append(tag)
        context["tags_by_category"] = tags_by_category

        return context
