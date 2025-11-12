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
from django.views import View
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator

from books.models import (
    Book,
    BookMaster,
    Language,
    FileUploadJob,
)
from books.forms import BookForm, BookFileUploadForm
from books.choices import ProcessingStatus
from books.tasks import process_file_upload


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
    """File upload view that queues background processing job"""

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
            # Read file content
            file_content = uploaded_file.read()
            filename = uploaded_file.name

            # Create FileUploadJob
            job = FileUploadJob.objects.create(
                book=book,
                created_by=self.request.user,
                auto_create_chapters=auto_create_chapters,
                status=ProcessingStatus.PENDING,
            )

            # Dispatch Celery task
            task = process_file_upload.delay(job.id, file_content, filename)

            # Store task ID for tracking
            job.celery_task_id = task.id
            job.save(update_fields=['celery_task_id'])

            messages.success(
                self.request,
                f"File '{filename}' uploaded successfully. Processing in background..."
            )
            return redirect(self.get_success_url())

        except ValidationError as e:
            messages.error(self.request, f"File validation failed: {str(e)}")
            return self.form_invalid(form)

        except Exception as e:
            messages.error(self.request, f"Unexpected error during file upload: {str(e)}")
            return self.form_invalid(form)


class UploadJobStatusView(LoginRequiredMixin, View):
    """API endpoint to check the status of a file upload job"""

    def get(self, request, job_id):
        """Return the current status of a file upload job"""
        try:
            job = get_object_or_404(
                FileUploadJob.objects.select_related('book', 'book__bookmaster'),
                id=job_id,
                book__bookmaster__owner=request.user,
            )

            response_data = {
                "job_id": job.id,
                "status": job.status,
                "book_id": job.book.id,
                "book_title": job.book.title,
                "auto_create_chapters": job.auto_create_chapters,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat(),
            }

            # Add results if completed
            if job.status == ProcessingStatus.COMPLETED:
                response_data.update({
                    "word_count": job.word_count,
                    "character_count": job.character_count,
                    "detected_chapter_count": job.detected_chapter_count,
                    "created_chapter_count": job.created_chapter_count,
                    "message": f"Successfully processed file. Created {job.created_chapter_count} chapters from {job.detected_chapter_count} detected.",
                })
            elif job.status == ProcessingStatus.FAILED:
                response_data.update({
                    "error": job.error_message,
                    "message": f"File processing failed: {job.error_message}",
                })
            elif job.status == ProcessingStatus.PROCESSING:
                response_data["message"] = "Processing file..."
            else:  # PENDING
                response_data["message"] = "Waiting to process file..."

            return JsonResponse(response_data)

        except FileUploadJob.DoesNotExist:
            return JsonResponse(
                {"error": "Upload job not found"},
                status=404
            )
