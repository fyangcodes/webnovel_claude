from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import (
    CreateView,
    DetailView,
    UpdateView,
    DeleteView,
)
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.db import transaction, models
from django.core.paginator import Paginator

from books.models import (
    Book,
    BookMaster,
    Language,
    ChapterMaster,
    Chapter,
)
from books.forms import BookForm, BookFileUploadForm
from books.choices import ChapterProgress
from books.utils import TextExtractor


# Book CRUD Views
class BookCreateView(LoginRequiredMixin, CreateView):
    model = Book
    form_class = BookForm
    template_name = "books/book/form.html"

    def get_success_url(self):
        return reverse_lazy(
            "books:bookmaster_detail",
            kwargs={"pk": self.kwargs.get("bookmaster_pk")},
        )

    def form_valid(self, form):
        form.instance.owner = self.request.user
        # Set the bookmaster field from the URL kwarg
        bookmaster_pk = self.kwargs.get("bookmaster_pk")
        if bookmaster_pk:
            bookmaster = get_object_or_404(BookMaster, pk=bookmaster_pk)
            form.instance.bookmaster = bookmaster
            # Determine the language: GET/POST param or default to original
            language_id = self.request.GET.get("language") or self.request.POST.get(
                "language"
            )
            if language_id:
                try:
                    requested_language = Language.objects.get(pk=language_id)
                except Language.DoesNotExist:
                    messages.error(
                        self.request,
                        f"Language '{requested_language}' does not exist. Using original language.",
                    )
                    requested_language = bookmaster.original_language
            else:
                requested_language = bookmaster.original_language
            form.instance.language = requested_language
            # Check if a book in the requested language already exists for this bookmaster
            if Book.objects.filter(
                bookmaster=bookmaster, language=requested_language
            ).exists():
                messages.warning(
                    self.request,
                    f"A book in {requested_language.name} already exists for this work.",
                )
                return redirect("books:bookmaster_detail", pk=bookmaster_pk)
        return super().form_valid(form)


class BookDetailView(LoginRequiredMixin, DetailView):
    model = Book
    template_name = "books/book/detail.html"
    context_object_name = "book"

    def get_queryset(self):
        return (
            Book.objects.filter(bookmaster__owner=self.request.user)
            .select_related("bookmaster", "language")
            .prefetch_related("bookmaster__book_genres__genre")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all chapters ordered by chapter number
        chapters_queryset = self.object.chapters.all().order_by(
            "chaptermaster__chapter_number"
        )

        # Add pagination
        paginator = Paginator(chapters_queryset, 20)  # 20 chapters per page
        page_number = self.request.GET.get("page")
        chapters_page = paginator.get_page(page_number)

        context["chapters"] = chapters_page
        context["chapter_create_url"] = reverse_lazy(
            "books:chapter_create", kwargs={"book_pk": self.object.pk}
        )
        context["bookmaster"] = self.object.bookmaster

        # Add genres with localized names
        language_code = self.object.language.code if self.object.language else "en"
        genres_with_localized = []
        for bg in self.object.bookmaster.book_genres.all():
            genres_with_localized.append(
                {
                    "genre": bg.genre,
                    "localized_name": bg.genre.get_localized_name(language_code),
                    "order": bg.order,
                }
            )
        context["genres"] = genres_with_localized

        # Add all available languages for translation modal
        context["all_languages"] = Language.objects.all().order_by("name")

        return context


class BookUpdateView(LoginRequiredMixin, UpdateView):
    model = Book
    form_class = BookForm
    template_name = "books/book/form.html"
    context_object_name = "book"

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bookmaster"] = self.object.bookmaster
        return context


class BookDeleteView(LoginRequiredMixin, DeleteView):
    model = Book
    template_name = "books/book/confirm_delete.html"

    def get_queryset(self):
        return Book.objects.filter(bookmaster__owner=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Book deleted successfully.")
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy(
            "books:bookmaster_detail", kwargs={"pk": self.object.bookmaster.pk}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bookmaster"] = self.object.bookmaster
        return context


class BookFileUploadView(LoginRequiredMixin, FormView):
    """Async file upload view for books"""

    form_class = BookFileUploadForm
    template_name = "books/book/upload_file.html"

    def get_object(self):
        return get_object_or_404(
            Book.objects.select_related("bookmaster"),
            pk=self.kwargs["pk"],
            bookmaster__owner=self.request.user,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["book"] = self.get_object()
        return context

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.kwargs["pk"]})

    def form_valid(self, form):
        book = self.get_object()
        uploaded_file = form.cleaned_data["file"]
        auto_create_chapters = form.cleaned_data["auto_create_chapters"]

        try:
            # Extract text and chapters using the utility function
            result = TextExtractor.extract_text_from_file(
                uploaded_file, include_chapters=True
            )

            if auto_create_chapters and result.get("chapters"):
                created_count = self._create_chapters_from_upload(
                    book, result["chapters"]
                )
                messages.success(
                    self.request,
                    f"Successfully processed file and created {created_count} chapters "
                    f"from {result['chapter_count']} detected chapters.",
                )
                # Update result for JSON response
                result["created_chapter_count"] = created_count
            else:
                # Just extract text without creating chapters
                messages.info(
                    self.request,
                    f"File processed successfully. {result['word_count']} words, "
                    f"{result['character_count']} characters found. "
                    f"{result['chapter_count']} potential chapters detected.",
                )
                result["created_chapter_count"] = 0

            # If this is an AJAX request, return JSON response
            if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
                message = (
                    f"File processed successfully. Created {result['created_chapter_count']} chapters."
                    if auto_create_chapters
                    else f"File processed successfully. {result['chapter_count']} potential chapters detected."
                )
                return JsonResponse(
                    {
                        "success": True,
                        "message": message,
                        "redirect_url": str(self.get_success_url()),
                        "stats": {
                            "word_count": result["word_count"],
                            "character_count": result["character_count"],
                            "detected_chapter_count": result["chapter_count"],
                            "created_chapter_count": result["created_chapter_count"],
                        },
                    }
                )

        except ValidationError as e:
            error_msg = str(e)
            messages.error(self.request, f"File processing failed: {error_msg}")

            if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": error_msg}, status=400)

        except Exception as e:
            error_msg = f"Unexpected error during file processing: {str(e)}"
            messages.error(self.request, error_msg)

            if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": error_msg}, status=500)

        return super().form_valid(form)

    @transaction.atomic
    def _create_chapters_from_upload(self, book, chapters_data):
        """Create chapters and chapter masters from extracted data"""
        # Get the highest existing chapter number for this bookmaster
        existing_max_number = (
            ChapterMaster.objects.filter(bookmaster=book.bookmaster).aggregate(
                max_number=models.Max("chapter_number")
            )["max_number"]
            or 0
        )

        created_chapters = 0
        for i, chapter_info in enumerate(chapters_data, 1):
            try:
                # Check if ChapterMaster with this number already exists
                chapter_number = existing_max_number + i
                chapter_master, _ = ChapterMaster.objects.get_or_create(
                    bookmaster=book.bookmaster,
                    chapter_number=chapter_number,
                    defaults={"canonical_title": chapter_info["title"]},
                )

                # If ChapterMaster wasn't created, it means it already exists
                # Check if Chapter already exists for this book
                if not Chapter.objects.filter(
                    chaptermaster=chapter_master, book=book
                ).exists():
                    # Create Chapter - let the model handle word/character count calculation
                    chapter = Chapter.objects.create(
                        title=chapter_info["title"],
                        chaptermaster=chapter_master,
                        book=book,
                        content=chapter_info["content"],
                        progress=ChapterProgress.DRAFT,
                        is_public=False,
                    )

                    created_chapters += 1

            except Exception as e:
                # Log the error but continue with other chapters
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Error creating chapter {i}: {str(e)}")
                continue

        # Update book metadata after all chapters are created
        book.update_metadata()
        return created_chapters
