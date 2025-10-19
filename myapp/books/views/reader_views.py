from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView
from django.http import Http404
from django.core.paginator import Paginator

from books.models import Book, Chapter, Language, Genre, BookGenre


class BookListView(ListView):
    """Reader-friendly book listing page"""

    model = Book
    template_name = "books/reader/book_list.html"
    context_object_name = "books"
    paginate_by = 12

    def get_queryset(self):
        language_code = self.kwargs.get("language_code")
        language = get_object_or_404(Language, code=language_code)

        return (
            Book.objects.filter(language=language, is_public=True)
            .select_related("bookmaster", "language")
            .prefetch_related("chapters")
            .order_by("-published_at", "-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")
        context["current_language"] = get_object_or_404(Language, code=language_code)
        context["languages"] = Language.objects.all().order_by("name")
        context["genres"] = Genre.objects.all().order_by("name")

        # Add published chapters info for each book
        books_with_info = []
        for book in context["books"]:
            published_chapters = book.chapters.filter(is_public=True)
            published_count = published_chapters.count()

            # Calculate reading time
            total_minutes = sum(
                chapter.reading_time_minutes for chapter in published_chapters
            )
            if total_minutes < 60:
                reading_time = f"{total_minutes} min" if total_minutes > 0 else None
            else:
                hours = total_minutes // 60
                minutes = total_minutes % 60
                if minutes == 0:
                    reading_time = f"{hours} hr"
                else:
                    reading_time = f"{hours} hr {minutes} min"

            # Add the info to the book object
            book.published_chapters_count = published_count
            book.reading_time_formatted = reading_time
            books_with_info.append(book)

        context["books"] = books_with_info
        return context


class GenreBookListView(ListView):
    """Genre-filtered book listing page"""

    model = Book
    template_name = "books/reader/genre_book_list.html"
    context_object_name = "books"
    paginate_by = 12

    def get_queryset(self):
        language_code = self.kwargs.get("language_code")
        genre_slug = self.kwargs.get("genre_slug")

        language = get_object_or_404(Language, code=language_code)
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
            .prefetch_related("chapters")
            .order_by("-published_at", "-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = self.kwargs.get("language_code")
        genre_slug = self.kwargs.get("genre_slug")

        context["current_language"] = get_object_or_404(Language, code=language_code)
        context["languages"] = Language.objects.all().order_by("name")
        context["genres"] = Genre.objects.all().order_by("name")
        context["current_genre"] = get_object_or_404(Genre, slug=genre_slug)

        # Add published chapters info for each book
        books_with_info = []
        for book in context["books"]:
            published_chapters = book.chapters.filter(is_public=True)
            published_count = published_chapters.count()

            # Calculate reading time
            total_minutes = sum(
                chapter.reading_time_minutes for chapter in published_chapters
            )
            if total_minutes < 60:
                reading_time = f"{total_minutes} min" if total_minutes > 0 else None
            else:
                hours = total_minutes // 60
                minutes = total_minutes % 60
                if minutes == 0:
                    reading_time = f"{hours} hr"
                else:
                    reading_time = f"{hours} hr {minutes} min"

            # Add the info to the book object
            book.published_chapters_count = published_count
            book.reading_time_formatted = reading_time
            books_with_info.append(book)

        context["books"] = books_with_info
        return context


class BookDetailView(DetailView):
    """Reader-friendly book detail page with chapter list"""

    model = Book
    template_name = "books/reader/book_detail.html"
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
    template_name = "books/reader/chapter_detail.html"
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
