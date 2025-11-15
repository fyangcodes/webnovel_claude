from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import ListView, DetailView, TemplateView
from django.core.paginator import Paginator
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.db.models import Case, When

from books.models import Book, Chapter, Language, Genre, BookGenre, BookMaster, Section, Tag
from books.utils.search import BookSearchService
from reader import cache

class BaseBookListView(ListView):
    """Base view with common reader functionality"""

    model = Book
    context_object_name = "books"
    paginate_by = 12

    def get_language(self):
        """
        Get language from URL kwargs and check visibility permissions.

        Non-staff users can only access public languages.
        Staff users can access all languages (including private ones).

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

    def add_localized_genre_names(self, genres, language_code):
        """
        Add localized names to genre objects.

        Also adds parent genre localized name if genre has a parent.
        """
        for genre in genres:
            genre.localized_name = genre.get_localized_name(language_code)
            if genre.parent:
                genre.parent_localized_name = genre.parent.get_localized_name(language_code)
        return genres

    def add_localized_section_names(self, sections, language_code):
        """Add localized names to section objects"""
        for section in sections:
            section.localized_name = section.get_localized_name(language_code)
        return sections

    def enrich_books_with_metadata(self, books, language_code):
        """
        Add published chapters count, total views, localized genres, and section to books.

        Enhanced to include:
        - Section localized name
        - Genre parent hierarchy
        - Tags (if applicable)
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
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")

        context["current_language"] = self.get_language()

        # Use cached languages (eliminates 1 query per request)
        # Staff sees all languages, readers see only public languages
        context["languages"] = cache.get_cached_languages(user=self.request.user)

        # Add sections with localized names (cached)
        sections = cache.get_cached_sections(user=self.request.user)
        context["sections"] = self.add_localized_section_names(sections, language_code)

        # Use hierarchical genre structure grouped by section (cached)
        # This replaces the old flat genre list
        genres_hierarchical = cache.get_cached_genres()

        # Add localized names to all genres in the hierarchical structure
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

        context["genres_hierarchical"] = genres_hierarchical

        # Also provide flat genre list for backward compatibility
        genres_flat = cache.get_cached_genres_flat()
        context["genres"] = self.add_localized_genre_names(genres_flat, language_code)

        # Add tags grouped by category (cached)
        tags_by_category = cache.get_cached_tags()
        # Add localized names to tags
        for category, tags in tags_by_category.items():
            for tag in tags:
                tag.localized_name = tag.get_localized_name(language_code)
        context["tags_by_category"] = tags_by_category

        # Enrich books with metadata (using cached chapter counts)
        context["books"] = self.enrich_books_with_metadata(
            context["books"], language_code
        )

        return context


class WelcomeView(TemplateView):
    """Welcome/Homepage with carousels and featured content"""

    template_name = "reader/welcome.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")
        language = get_object_or_404(Language, code=language_code)

        # Check if user can access this language
        user = self.request.user
        is_staff = user.is_authenticated and user.is_staff
        if not language.is_public and not is_staff:
            raise Http404("Language not found")

        context["current_language"] = language

        # Use cached languages (eliminates 1 query per request)
        # Staff sees all languages, readers see only public languages
        context["languages"] = cache.get_cached_languages(user=self.request.user)

        # Add sections with localized names (cached)
        sections = cache.get_cached_sections(user=self.request.user)
        context["sections"] = self._add_localized_section_names(sections, language_code)

        # Use hierarchical genre structure grouped by section (cached)
        genres_hierarchical = cache.get_cached_genres()

        # Add localized names to all genres in the hierarchical structure
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

        context["genres_hierarchical"] = genres_hierarchical

        # Flat genre list for backward compatibility
        all_genres = cache.get_cached_genres_flat()
        context["genres"] = self._add_localized_names(all_genres, language_code)

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
            context["featured_books"] = self._enrich_books(featured_books, language_code)
        else:
            context["featured_books"] = []

        # Recently updated books - cached (eliminates annotated query + N+1)
        recently_updated = cache.get_cached_recently_updated(language_code, limit=6)
        context["recently_updated"] = self._enrich_books(
            recently_updated, language_code
        )

        # New arrivals - cached (eliminates query + N+1)
        new_arrivals = cache.get_cached_new_arrivals(language_code, limit=6)
        context["new_arrivals"] = self._enrich_books(new_arrivals, language_code)

        return context

    def _add_localized_names(self, genres, language_code):
        """Add localized names to genre objects"""
        for genre in genres:
            genre.localized_name = genre.get_localized_name(language_code)
            if genre.parent:
                genre.parent_localized_name = genre.parent.get_localized_name(language_code)
            if genre.section:
                genre.section_localized_name = genre.section.get_localized_name(language_code)
        return genres

    def _add_localized_section_names(self, sections, language_code):
        """Add localized names to section objects"""
        for section in sections:
            section.localized_name = section.get_localized_name(language_code)
        return sections

    def _enrich_books(self, books, language_code):
        """
        Add published chapters count, total views, localized genres, and section to books.

        Enhanced to include section and genre hierarchy.
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

            # Add localized names to each genre (including parent and section)
            for genre in book.bookmaster.genres.all():
                genre.localized_name = genre.get_localized_name(language_code)
                if genre.parent:
                    genre.parent_localized_name = genre.parent.get_localized_name(language_code)
                if genre.section:
                    genre.section_localized_name = genre.section.get_localized_name(language_code)

            enriched_books.append(book)

        return enriched_books


class BookListView(BaseBookListView):
    """Reader-friendly book listing page with section/genre/tag filtering"""

    template_name = "reader/book_list.html"

    def get_queryset(self):
        language = self.get_language()
        queryset = Book.objects.filter(language=language, is_public=True)

        # Filter by section if specified (NEW)
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

        # Filter by tag if specified (NEW)
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

        # Add breadcrumb data (NEW)
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


class GenreBookListView(BaseBookListView):
    """Redirect to query-based filtering for genres"""

    def get(self, request, *args, **kwargs):
        language_code = kwargs.get("language_code")
        genre_slug = kwargs.get("genre_slug")

        # Build URL with query parameters
        url = reverse("reader:book_list", args=[language_code])
        return redirect(f"{url}?genre={genre_slug}")


class TagBookListView(BaseBookListView):
    """Redirect to query-based filtering for tags"""

    def get(self, request, *args, **kwargs):
        language_code = kwargs.get("language_code")
        tag_slug = kwargs.get("tag_slug")

        # Build URL with query parameters
        url = reverse("reader:book_list", args=[language_code])
        return redirect(f"{url}?tag={tag_slug}")


class BookSearchView(BaseBookListView):
    """
    Keyword search view with filtering.

    URL: /<language_code>/search/?q=<query>&section=<slug>&genre=<slug>...

    Uses BookSearchService for weighted keyword search across sections, genres, tags,
    and entities. Supports all standard filters (section, genre, tag, status).
    """
    template_name = "reader/search.html"
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


class BookDetailView(DetailView):
    """Reader-friendly book detail page with chapter list and taxonomy"""

    model = Book
    template_name = "reader/book_detail.html"
    context_object_name = "book"
    slug_field = "slug"
    slug_url_kwarg = "book_slug"

    def get_queryset(self):
        language_code = self.kwargs.get("language_code")
        language = get_object_or_404(Language, code=language_code)

        # Check if user can access this language
        user = self.request.user
        is_staff = user.is_authenticated and user.is_staff
        if not language.is_public and not is_staff:
            raise Http404("Language not found")

        return (
            Book.objects.filter(language=language, is_public=True)
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
        language_code = self.kwargs.get("language_code")
        context["current_language"] = get_object_or_404(Language, code=language_code)

        # Use cached languages for language switcher
        # Staff sees all languages, readers see only public languages
        context["languages"] = cache.get_cached_languages(user=self.request.user)

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


class ChapterDetailView(DetailView):
    """Reader-friendly chapter reading page"""

    model = Chapter
    template_name = "reader/chapter_detail.html"
    context_object_name = "chapter"
    slug_field = "slug"
    slug_url_kwarg = "chapter_slug"

    def get_queryset(self):
        language_code = self.kwargs.get("language_code")
        book_slug = self.kwargs.get("book_slug")

        # Ensure the language matches the URL
        language = get_object_or_404(Language, code=language_code)

        # Check if user can access this language
        user = self.request.user
        is_staff = user.is_authenticated and user.is_staff
        if not language.is_public and not is_staff:
            raise Http404("Language not found")

        book = get_object_or_404(
            Book, slug=book_slug, language=language, is_public=True
        )

        return Chapter.objects.filter(book=book, is_public=True).select_related(
            "book__bookmaster", "book__language", "chaptermaster"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")
        context["current_language"] = get_object_or_404(Language, code=language_code)
        context["book"] = self.object.book

        # Use cached languages for language switcher
        # Staff sees all languages, readers see only public languages
        context["languages"] = cache.get_cached_languages(user=self.request.user)

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
