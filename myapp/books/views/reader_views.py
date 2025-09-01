from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView
from django.http import Http404

from books.models import Book, Chapter, Language


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
        
        # Only show published chapters to readers, ordered by chapter number
        context["chapters"] = (
            self.object.chapters.filter(is_public=True)
            .select_related("chaptermaster")
            .order_by("chaptermaster__chapter_number")
        )
        
        # Reading progress context
        context["total_chapters"] = context["chapters"].count()
        context["total_words"] = sum(chapter.word_count for chapter in context["chapters"])
        
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
        book = get_object_or_404(Book, slug=book_slug, language=language, is_public=True)
        
        return (
            Chapter.objects.filter(book=book, is_public=True)
            .select_related("book__bookmaster", "book__language", "chaptermaster")
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
        context["previous_chapter"] = (
            published_chapters.filter(
                chaptermaster__chapter_number__lt=current_chapter_number
            ).last()
        )
        context["next_chapter"] = (
            published_chapters.filter(
                chaptermaster__chapter_number__gt=current_chapter_number
            ).first()
        )
        
        # Reading progress
        context["chapter_position"] = (
            published_chapters.filter(
                chaptermaster__chapter_number__lte=current_chapter_number
            ).count()
        )
        context["total_chapters"] = published_chapters.count()
        
        return context