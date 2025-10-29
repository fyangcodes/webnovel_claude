from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView, TemplateView
from django.http import Http404
from django.core.paginator import Paginator
from django.db.models import Count, Max

from books.models import Book, Chapter, Language, Genre, BookGenre


class BaseTailwindView(TemplateView):
    """
    Base view for reader-tw templates providing common context.

    This view provides the basic context needed by reader-tw/base.html:
    - current_language: Language object from URL
    - languages: All available languages
    - genres: All genres with localized names
    """

    def get_language(self):
        """Get language from URL kwargs"""
        language_code = self.kwargs.get("language_code")
        return get_object_or_404(Language, code=language_code)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")

        # Current language
        context["current_language"] = self.get_language()

        # All available languages for language switcher
        context["languages"] = Language.objects.all().order_by("name")

        # All genres with localized names for genres dropdown
        genres = Genre.objects.all().order_by("name")
        for genre in genres:
            genre.localized_name = genre.get_localized_name(language_code)
        context["genres"] = genres

        return context


class TailwindExampleView(BaseTailwindView):
    """
    Example view demonstrating how to use BaseTailwindView.

    To use this view in your own views:
    1. Inherit from BaseTailwindView
    2. Set template_name to your reader-tw template
    3. Override get_context_data() to add custom context
    """
    template_name = "reader-tw/example.html"

    def get_context_data(self, **kwargs):
        # Call parent to get basic context (current_language, languages, genres)
        context = super().get_context_data(**kwargs)

        # Add any custom context here
        # context["custom_data"] = "your data"

        return context


class BaseBookListView(ListView):
    """Base view with common reader functionality"""

    model = Book
    context_object_name = "books"
    paginate_by = 12

    def get_language(self):
        """Get language from URL kwargs"""
        language_code = self.kwargs.get("language_code")
        return get_object_or_404(Language, code=language_code)

    def add_localized_genre_names(self, genres, language_code):
        """Add localized names to genre objects"""
        for genre in genres:
            genre.localized_name = genre.get_localized_name(language_code)
        return genres

    def enrich_books_with_metadata(self, books, language_code):
        """Add published chapters count, reading time, and localized genres to books"""
        enriched_books = []
        for book in books:
            published_chapters = book.chapters.filter(is_public=True)
            published_count = published_chapters.count()    

            # Add the info to the book object
            book.published_chapters_count = published_count

            # Add localized names to each genre
            for genre in book.bookmaster.genres.all():
                genre.localized_name = genre.get_localized_name(language_code)

            enriched_books.append(book)

        return enriched_books

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")

        context["current_language"] = self.get_language()
        context["languages"] = Language.objects.all().order_by("name")

        # Add localized genre names for navigation
        genres = Genre.objects.all().order_by("name")
        context["genres"] = self.add_localized_genre_names(genres, language_code)

        # Enrich books with metadata
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

        context["current_language"] = language
        context["languages"] = Language.objects.all().order_by("name")

        # Get all genres with localized names
        genres = Genre.objects.all().order_by("name")
        for genre in genres:
            genre.localized_name = genre.get_localized_name(language_code)
        context["genres"] = genres

        # Featured/Popular books (books with most chapters)
        featured_books = (
            Book.objects.filter(language=language, is_public=True)
            .select_related("bookmaster", "language")
            .prefetch_related("chapters", "bookmaster__genres")
            .annotate(chapter_count=Count("chapters"))
            .order_by("-chapter_count", "-published_at")[:6]
        )
        context["featured_books"] = self._enrich_books(featured_books, language_code)

        # Recently updated books (by most recent chapter published_at)
        recently_updated = (
            Book.objects.filter(language=language, is_public=True)
            .select_related("bookmaster", "language")
            .prefetch_related("chapters", "bookmaster__genres")
            .annotate(latest_chapter=Max("chapters__published_at"))
            .order_by("-latest_chapter")[:6]
        )
        context["recently_updated"] = self._enrich_books(recently_updated, language_code)

        # New arrivals (recently published books)
        new_arrivals = (
            Book.objects.filter(language=language, is_public=True)
            .select_related("bookmaster", "language")
            .prefetch_related("chapters", "bookmaster__genres")
            .order_by("-published_at")[:6]
        )
        context["new_arrivals"] = self._enrich_books(new_arrivals, language_code)
        return context

    def _enrich_books(self, books, language_code):
        """Add published chapters count and localized genres to books"""
        enriched_books = []
        for book in books:
            published_chapters = book.chapters.filter(is_public=True)
            book.published_chapters_count = published_chapters.count()

            # Add localized names to each genre
            for genre in book.bookmaster.genres.all():
                genre.localized_name = genre.get_localized_name(language_code)

            enriched_books.append(book)

        return enriched_books


class GenreListView(TemplateView):
    """Genre overview page showing all genres"""

    template_name = "reader/genre_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")
        language = get_object_or_404(Language, code=language_code)

        context["current_language"] = language
        context["languages"] = Language.objects.all().order_by("name")

        # Get all genres with book counts for this language
        genres = Genre.objects.all().order_by("name")

        enriched_genres = []
        for genre in genres:
            # Get localized name
            genre.localized_name = genre.get_localized_name(language_code)

            # Get bookmaster IDs for this genre
            bookmaster_ids = BookGenre.objects.filter(genre=genre).values_list(
                "bookmaster_id", flat=True
            )

            # Count books in this language with this genre
            genre.book_count = Book.objects.filter(
                language=language, is_public=True, bookmaster_id__in=bookmaster_ids
            ).count()

            # Get preview books (top 3 for this genre)
            genre.preview_books = (
                Book.objects.filter(
                    language=language, is_public=True, bookmaster_id__in=bookmaster_ids
                )
                .select_related("bookmaster", "language")
                .prefetch_related("chapters")
                .order_by("-published_at")[:3]
            )

            # Enrich preview books with chapter counts
            for book in genre.preview_books:
                book.published_chapters_count = book.chapters.filter(
                    is_public=True
                ).count()

            enriched_genres.append(genre)

        context["genres"] = enriched_genres
        context["all_genres"] = Genre.objects.all().order_by("name")

        return context


class BookListView(BaseBookListView):
    """Reader-friendly book listing page"""

    template_name = "reader/book_list.html"

    def get_queryset(self):
        language = self.get_language()

        return (
            Book.objects.filter(language=language, is_public=True)
            .select_related("bookmaster", "language")
            .prefetch_related("chapters", "bookmaster__genres")
            .order_by("-published_at", "-created_at")
        )


class GenreBookListView(BaseBookListView):
    """Genre-filtered book listing page"""

    template_name = "reader/genre_book_list.html"

    def get_queryset(self):
        language = self.get_language()
        genre_slug = self.kwargs.get("genre_slug")
        genre = get_object_or_404(Genre, slug=genre_slug)

        # Get bookmaster IDs that have this genre
        bookmaster_ids = BookGenre.objects.filter(genre=genre).values_list(
            "bookmaster_id", flat=True
        )

        return (
            Book.objects.filter(
                language=language, is_public=True, bookmaster_id__in=bookmaster_ids
            )
            .select_related("bookmaster", "language")
            .prefetch_related("chapters", "bookmaster__genres")
            .order_by("-published_at", "-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        genre_slug = self.kwargs.get("genre_slug")
        context["current_genre"] = get_object_or_404(Genre, slug=genre_slug)
        return context


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

        return (
            Book.objects.filter(language=language, is_public=True)
            .select_related("bookmaster", "language")
            .prefetch_related("chapters__chaptermaster")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")
        context["current_language"] = get_object_or_404(Language, code=language_code)

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

        # Navigation context - previous/next chapters
        current_chapter_number = self.object.chaptermaster.chapter_number
        published_chapters = (
            Chapter.objects.filter(book=self.object.book, is_public=True)
            .select_related("chaptermaster")
            .order_by("chaptermaster__chapter_number")
        )

        # Find previous and next chapters
        context["previous_chapter"] = published_chapters.filter(
            chaptermaster__chapter_number__lt=current_chapter_number
        ).last()
        context["next_chapter"] = published_chapters.filter(
            chaptermaster__chapter_number__gt=current_chapter_number
        ).first()

        # Reading progress
        context["chapter_position"] = published_chapters.filter(
            chaptermaster__chapter_number__lte=current_chapter_number
        ).count()
        context["total_chapters"] = published_chapters.count()

        return context
