from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import ListView, DetailView, TemplateView
from django.core.paginator import Paginator
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404

from books.models import Book, Chapter, Language, Genre, BookGenre, BookMaster
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
        """Add localized names to genre objects"""
        for genre in genres:
            genre.localized_name = genre.get_localized_name(language_code)
        return genres

    def enrich_books_with_metadata(self, books, language_code):
        """Add published chapters count, total views, and localized genres to books"""
        enriched_books = []
        for book in books:
            # Use cached chapter count (eliminates N+1 query)
            book.published_chapters_count = cache.get_cached_chapter_count(book.id)

            # Add total chapter views (eliminates N+1 query)
            book.total_chapter_views = cache.get_cached_total_chapter_views(book.id)

            # Add localized names to each genre
            for genre in book.bookmaster.genres.all():
                genre.localized_name = genre.get_localized_name(language_code)

            enriched_books.append(book)

        return enriched_books

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")

        context["current_language"] = self.get_language()

        # Use cached languages (eliminates 1 query per request)
        # Staff sees all languages, readers see only public languages
        context["languages"] = cache.get_cached_languages(user=self.request.user)

        # Add localized genre names for navigation (cached)
        genres = cache.get_cached_genres()
        context["genres"] = self.add_localized_genre_names(genres, language_code)

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

        # Use cached genres (eliminates 1 query per request)
        all_genres = cache.get_cached_genres()
        context["genres"] = self._add_localized_names(all_genres, language_code)

        # Get featured genres from settings (only show if defined)
        featured_genre_ids = getattr(settings, "FEATURED_GENRES", [])
        if featured_genre_ids:
            featured_genres = cache.get_cached_featured_genres(featured_genre_ids)
            context["featured_genres"] = self._add_localized_names(
                featured_genres, language_code
            )
        else:
            context["featured_genres"] = []

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
        return genres

    def _enrich_books(self, books, language_code):
        """Add published chapters count, total views, and localized genres to books"""
        enriched_books = []
        for book in books:
            # Use cached chapter count (eliminates N+1 query)
            book.published_chapters_count = cache.get_cached_chapter_count(book.id)

            # Add total chapter views (eliminates N+1 query)
            book.total_chapter_views = cache.get_cached_total_chapter_views(book.id)

            # Add localized names to each genre
            for genre in book.bookmaster.genres.all():
                genre.localized_name = genre.get_localized_name(language_code)

            enriched_books.append(book)

        return enriched_books


class BookListView(BaseBookListView):
    """Reader-friendly book listing page"""

    template_name = "reader/book_list.html"

    def get_queryset(self):
        language = self.get_language()
        queryset = Book.objects.filter(language=language, is_public=True)

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

        # Filter by progress/status if specified
        progress = self.request.GET.get("status")
        if progress and progress in ["draft", "ongoing", "completed"]:
            queryset = queryset.filter(progress=progress)

        return (
            queryset.select_related("bookmaster", "language")
            .prefetch_related("chapters", "bookmaster__genres")
            .order_by("-published_at", "-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add current filter values to context
        context["selected_genre"] = self.request.GET.get("genre", "")
        context["selected_status"] = self.request.GET.get("status", "")

        return context


class GenreBookListView(BaseBookListView):
    """Redirect to query-based filtering"""

    def get(self, request, *args, **kwargs):
        language_code = kwargs.get("language_code")
        genre_slug = kwargs.get("genre_slug")

        # Build URL with query parameters
        url = reverse("reader:book_list", args=[language_code])
        return redirect(f"{url}?genre={genre_slug}")


class BookDetailView(DetailView):
    """Reader-friendly book detail page with chapter list"""

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
            .select_related("bookmaster", "language")
            .prefetch_related("chapters__chaptermaster")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")
        context["current_language"] = get_object_or_404(Language, code=language_code)

        # Use cached languages for language switcher
        # Staff sees all languages, readers see only public languages
        context["languages"] = cache.get_cached_languages(user=self.request.user)

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
