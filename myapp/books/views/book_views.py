import json
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import (
    CreateView,
    DetailView,
    UpdateView,
    DeleteView,
    ListView,
)
from django.views.generic.edit import FormView
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
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
    TranslationJob,
)
from books.forms import BookForm, BookFileUploadForm
from books.choices import BookProgress, ChapterProgress, ProcessingStatus
from books.utils import extract_text_from_file


# Book CRUD Views
class BookCreateView(LoginRequiredMixin, CreateView):
    model = Book
    form_class = BookForm
    template_name = "books/book/form.html"

    def get_success_url(self):
        return reverse_lazy(
            "books_admin:bookmaster_detail",
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
                return redirect("books_admin:bookmaster_detail", pk=bookmaster_pk)
        return super().form_valid(form)


class BookDetailView(LoginRequiredMixin, DetailView):
    model = Book
    template_name = "books/book/detail.html"
    context_object_name = "book"

    def get_queryset(self):
        return Book.objects.filter(bookmaster__owner=self.request.user)

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
            "books_admin:chapter_create", kwargs={"book_pk": self.object.pk}
        )
        context["bookmaster"] = self.object.bookmaster

        # Add all available languages for translation modal
        context["all_languages"] = Language.objects.all().order_by("name")

        return context


class BookUpdateView(LoginRequiredMixin, UpdateView):
    model = Book
    form_class = BookForm
    template_name = "books/book/form.html"
    context_object_name = "book"

    def get_success_url(self):
        return reverse_lazy("books_admin:book_detail", kwargs={"pk": self.object.pk})

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
        book = self.get_object()
        # Remove uploaded_file reference as it's not in the new model
        # if book.uploaded_file:
        #     book.uploaded_file.delete()
        messages.success(request, "Book deleted successfully.")
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy(
            "books_admin:bookmaster_detail", kwargs={"pk": self.object.bookmaster.pk}
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
        return reverse_lazy("books_admin:book_detail", kwargs={"pk": self.kwargs["pk"]})

    def form_valid(self, form):
        book = self.get_object()
        uploaded_file = form.cleaned_data["file"]
        auto_create_chapters = form.cleaned_data["auto_create_chapters"]

        try:
            # Extract text and chapters using the utility function
            result = extract_text_from_file(uploaded_file, include_chapters=True)

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

                    # Generate excerpt if content exists
                    chapter.generate_excerpt()

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


class BatchChapterActionView(LoginRequiredMixin, View):
    """Handle batch operations on chapters within a book"""

    def post(self, request, book_pk):
        try:
            # Get the book and verify ownership
            book = get_object_or_404(Book, pk=book_pk)
            if book.bookmaster.owner != request.user:
                return JsonResponse({"success": False, "message": "Permission denied"})

            # Parse JSON data
            data = json.loads(request.body)
            action = data.get("action")
            chapter_ids = data.get("chapter_ids", [])

            if not action or not chapter_ids:
                return JsonResponse(
                    {"success": False, "message": "Missing required data"}
                )

            # Get the chapters
            chapters = Chapter.objects.filter(id__in=chapter_ids, book=book)

            if not chapters.exists():
                return JsonResponse(
                    {"success": False, "message": "No valid chapters found"}
                )

            # Perform the requested action
            result = self._perform_action(action, chapters, data)

            return JsonResponse(result)

        except json.JSONDecodeError:
            return JsonResponse({"success": False, "message": "Invalid JSON data"})
        except Exception as e:
            return JsonResponse(
                {"success": False, "message": f"An error occurred: {str(e)}"}
            )

    def _perform_action(self, action, chapters, data):
        """Perform the batch action on the given chapters"""
        success_count = 0
        error_count = 0
        errors = []

        for chapter in chapters:
            try:
                if action == "publish":
                    chapter.publish()
                    success_count += 1
                elif action == "unpublish":
                    chapter.unpublish()
                    success_count += 1
                elif action == "change_status":
                    status = data.get("status")
                    if status in [choice[0] for choice in ChapterProgress.choices]:
                        chapter.progress = status
                        chapter.save()
                        success_count += 1
                    else:
                        errors.append(f"Invalid status for {chapter.title}")
                        error_count += 1
                elif action == "translate":
                    target_language_code = data.get("target_language")
                    if target_language_code:
                        self._create_translation_job(chapter, target_language_code)
                        success_count += 1
                    else:
                        errors.append(
                            f"No target language specified for {chapter.title}"
                        )
                        error_count += 1
                elif action == "delete":
                    chapter_title = chapter.title
                    chapter.delete()
                    success_count += 1
                else:
                    errors.append(f"Unknown action: {action}")
                    error_count += 1
            except Exception as e:
                errors.append(f"Error with {chapter.title}: {str(e)}")
                error_count += 1

        # Prepare response message
        if success_count > 0 and error_count == 0:
            message = f"Successfully processed {success_count} chapter(s)"
        elif success_count > 0 and error_count > 0:
            message = f"Processed {success_count} chapter(s) successfully, {error_count} failed"
        else:
            message = f"Failed to process chapters: {'; '.join(errors[:3])}"
            if len(errors) > 3:
                message += f" (and {len(errors) - 3} more errors)"

        return {
            "success": success_count > 0,
            "message": message,
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,
        }

    def _create_translation_job(self, chapter, target_language_code):
        """Create translation job for a chapter"""
        target_language = get_object_or_404(Language, code=target_language_code)

        # Check if a translation job already exists for this combination
        existing_job = TranslationJob.objects.filter(
            chapter=chapter,
            target_language=target_language,
            status__in=[ProcessingStatus.PENDING, ProcessingStatus.PROCESSING],
        ).first()

        if not existing_job:
            TranslationJob.objects.create(
                chapter=chapter,
                target_language=target_language,
                created_by=self.request.user,
            )
            return 1
        return 0
