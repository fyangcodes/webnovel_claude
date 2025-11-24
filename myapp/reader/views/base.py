"""
Base view classes for the reader app.

This module contains:
- BaseReaderView: Universal base for all reader views with:
  - Language/section validation
  - Book enrichment (metadata, chapter counts, localized taxonomy)
  - Global navigation context (languages, sections, genres, tags)
- BaseBookListView: Base for list views with pagination
- BaseBookDetailView: Base for book detail views
- BaseSearchView: Base for search views with BookSearchService integration
"""

from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView
from django.http import Http404
from django.db.models import Case, When

from books.models import Book, Language, Section
from books.utils.search import BookSearchService
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

    def enrich_book_with_metadata(self, book, language_code):
        """
        Add metadata, chapter count, views, and localized taxonomy to a single book.

        This is the universal enrichment method used by both list and detail views.
        Enriches book with:
        - Published chapters count (cached)
        - Total chapter views (cached)
        - Localized section name
        - Localized author name
        - Localized genres with parent hierarchy
        - Localized tags grouped by category
        - Localized entities grouped by type

        Args:
            book: Book object to enrich
            language_code: Language code for localization

        Returns:
            The enriched book object (modified in-place)
        """
        # Use cached chapter count (eliminates N+1 query)
        book.published_chapters_count = cache.get_cached_chapter_count(book.id)

        # Add total chapter views (eliminates N+1 query)
        book.total_chapter_views = cache.get_cached_total_chapter_views(book.id)

        # Add localized section name if section exists
        if hasattr(book.bookmaster, 'section') and book.bookmaster.section:
            book.section_localized_name = book.bookmaster.section.get_localized_name(language_code)
        else:
            book.section_localized_name = None

        # Add localized author name if author exists
        if hasattr(book.bookmaster, 'author') and book.bookmaster.author:
            book.author_localized_name = book.bookmaster.author.get_localized_name(language_code)
        else:
            book.author_localized_name = None

        # Add localized names to each genre (including parent) and store on book
        genres = list(book.bookmaster.genres.all())
        for genre in genres:
            genre.localized_name = genre.get_localized_name(language_code)
            if genre.parent:
                genre.parent_localized_name = genre.parent.get_localized_name(language_code)
            # Add section localized name if genre has section
            if genre.section:
                genre.section_localized_name = genre.section.get_localized_name(language_code)
        book.enriched_genres = genres

        # Set primary genre for breadcrumb (first genre without parent)
        primary_genres = [g for g in genres if not g.parent]
        book.primary_genre = primary_genres[0] if primary_genres else None

        # Add localized tag names grouped by category
        tags = book.bookmaster.tags.all()
        tags_by_category = {}
        for tag in tags:
            tag.localized_name = tag.get_localized_name(language_code)
            category = tag.category
            if category not in tags_by_category:
                tags_by_category[category] = []
            tags_by_category[category].append(tag)
        book.tags_by_category = tags_by_category

        # Add entities grouped by type (exclude default order 999)
        entities = book.bookmaster.entities.exclude(order=999)
        entities_by_type = {}
        for entity in entities:
            # Get localized name from translations or fall back to source_name
            entity.localized_name = entity.translations.get(language_code, entity.source_name)
            entity_type_display = entity.get_entity_type_display()
            if entity_type_display not in entities_by_type:
                entities_by_type[entity_type_display] = []
            entities_by_type[entity_type_display].append(entity)
        book.entities_by_type = entities_by_type

        return book

    def enrich_books_with_metadata(self, books, language_code):
        """
        Add metadata to multiple books (list view helper).

        Calls enrich_book_with_metadata() for each book.

        Args:
            books: Queryset or list of Book objects
            language_code: Language code for localization

        Returns:
            List of enriched book objects
        """
        enriched_books = []
        for book in books:
            self.enrich_book_with_metadata(book, language_code)
            enriched_books.append(book)
        return enriched_books

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

        # Add all tags grouped by category for navigation/filtering (cached)
        all_tags_by_category = cache.get_cached_tags()
        # Add localized names to tags
        for category, tags in all_tags_by_category.items():
            for tag in tags:
                tag.localized_name = tag.get_localized_name(language_code)
        context["all_tags_by_category"] = all_tags_by_category

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

    def get_context_data(self, **kwargs):
        """Add enriched books to context"""
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")

        # Enrich books with metadata using inherited method from BaseReaderView
        context["books"] = self.enrich_books_with_metadata(
            context["books"], language_code
        )

        return context


class BaseSearchView(BaseBookListView):
    """
    Base class for search views with shared search logic.

    Provides:
    - Common get_queryset() with BookSearchService integration
    - Common search context (query, matched_keywords, search_time_ms)
    - Order preservation for search results

    Subclasses must implement:
    - get_section_for_search(): Return Section or None for scoping
    """

    template_name = "reader/search.html"
    model = Book
    paginate_by = 20

    def get_section_for_search(self):
        """
        Return Section instance for scoping search, or None for global search.

        Subclasses must override this method.
        """
        raise NotImplementedError("Subclasses must implement get_section_for_search()")

    def get_queryset(self):
        """
        Common search queryset logic using BookSearchService.

        Returns all books in section if no query provided.
        """
        query = self.request.GET.get('q', '').strip()

        if not query:
            self.search_results = None
            # Return all books in section when no query
            language = self.get_language()
            section = self.get_section_for_search()

            queryset = Book.objects.filter(
                language=language,
                is_public=True
            )

            if section:
                queryset = queryset.filter(bookmaster__section=section)

            # Apply filters
            genre_slug = self.request.GET.get('genre')
            if genre_slug:
                from books.models import Genre, BookGenre
                genre = Genre.objects.filter(slug=genre_slug).first()
                if genre:
                    bookmaster_ids = BookGenre.objects.filter(genre=genre).values_list(
                        "bookmaster_id", flat=True
                    )
                    queryset = queryset.filter(bookmaster_id__in=bookmaster_ids)

            tag_slug = self.request.GET.get('tag')
            if tag_slug:
                from books.models import Tag, BookTag
                tag = Tag.objects.filter(slug=tag_slug).first()
                if tag:
                    bookmaster_ids = BookTag.objects.filter(tag=tag).values_list(
                        "bookmaster_id", flat=True
                    )
                    queryset = queryset.filter(bookmaster_id__in=bookmaster_ids)

            status = self.request.GET.get('status')
            if status and status in ["draft", "ongoing", "completed"]:
                queryset = queryset.filter(progress=status)

            return (
                queryset.select_related("bookmaster", "bookmaster__section", "language")
                .prefetch_related("chapters", "bookmaster__genres", "bookmaster__genres__section", "bookmaster__tags")
                .order_by("-published_at", "-created_at")
            )

        # Get filter parameters
        genre_slug = self.request.GET.get('genre')
        tag_slug = self.request.GET.get('tag')
        status = self.request.GET.get('status')

        # Get section (implementation-specific)
        section = self.get_section_for_search()
        section_slug = section.slug if section else None

        # Get language
        language = self.get_language()

        # Perform search
        search_results = BookSearchService.search(
            query=query,
            language_code=language.code,
            section_slug=section_slug,
            genre_slug=genre_slug,
            tag_slug=tag_slug,
            status=status,
            limit=500  # Large limit, let Django paginate
        )

        self.search_results = search_results

        book_ids = [book.id for book in search_results['books']]

        if not book_ids:
            return Book.objects.none()

        queryset = Book.objects.filter(id__in=book_ids).select_related(
            "bookmaster", "bookmaster__section", "language"
        ).prefetch_related(
            "chapters", "bookmaster__genres", "bookmaster__genres__section", "bookmaster__tags"
        )

        # Preserve search ranking order
        preserved_order = Case(*[When(id=pk, then=pos) for pos, pk in enumerate(book_ids)])
        return queryset.order_by(preserved_order)

    def get_search_context(self):
        """
        Return common search context data.

        Includes:
        - search_query: The user's search query
        - matched_keywords: Keywords that matched in the search
        - search_time_ms: Time taken to perform the search
        - total_results: Total number of results
        - Filter values: selected_genre, selected_tag, selected_status
        """
        context = {}
        context['search_query'] = self.request.GET.get('q', '').strip()

        if hasattr(self, 'search_results') and self.search_results:
            context['matched_keywords'] = self.search_results['matched_keywords']
            context['search_time_ms'] = self.search_results['search_time_ms']
            context['total_results'] = self.search_results['total_results']
        else:
            context['matched_keywords'] = []
            context['search_time_ms'] = 0
            context['total_results'] = 0

        # Common filter values
        context["selected_genre"] = self.request.GET.get("genre", "")
        context["selected_tag"] = self.request.GET.get("tag", "")
        context["selected_status"] = self.request.GET.get("status", "")

        return context


class BaseBookDetailView(BaseReaderView, DetailView):
    """
    Base view for book detail pages.

    Provides:
    - Book queryset with proper select_related/prefetch_related
    - Book localization (section, genres, tags, entities)
    - All BaseReaderView functionality
    """

    model = None  # Will be set to Book in subclasses
    context_object_name = "book"
    slug_field = "slug"
    slug_url_kwarg = "book_slug"

    def get_context_data(self, **kwargs):
        """
        Add enriched book metadata to context.

        Uses the inherited enrich_book_with_metadata() method from BaseReaderView
        to add all metadata, localized taxonomy, chapter counts, and views.
        """
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")

        # Enrich book with all metadata using inherited method from BaseReaderView
        self.enrich_book_with_metadata(self.object, language_code)

        # Add convenience context variables for templates
        if self.object.section_localized_name:
            context["section_localized_name"] = self.object.section_localized_name
            context["section"] = self.object.bookmaster.section

        context["genres"] = self.object.enriched_genres
        context["tags_by_category"] = self.object.tags_by_category
        context["entities_by_type"] = self.object.entities_by_type

        return context
