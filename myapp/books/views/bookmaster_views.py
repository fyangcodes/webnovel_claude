from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    CreateView,
    ListView,
    DetailView,
    UpdateView,
    DeleteView,
)
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import get_object_or_404
import json

from books.models import BookMaster, ChapterMaster, Chapter, Language, TranslationJob
from books.forms import BookMasterForm
from books.choices import ChapterProgress, ProcessingStatus


class BookMasterCreateView(LoginRequiredMixin, CreateView):
    model = BookMaster
    form_class = BookMasterForm
    template_name = "books/bookmaster/form.html"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(
            "books_admin:bookmaster_detail", kwargs={"pk": self.object.pk}
        )


class BookMasterListView(LoginRequiredMixin, ListView):
    model = BookMaster
    template_name = "books/bookmaster/list.html"
    context_object_name = "bookmasters"

    def get_queryset(self):
        return BookMaster.objects.filter(owner=self.request.user).prefetch_related(
            "chaptermasters", "books__language"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add extra information for each bookmaster
        bookmasters_with_info = []
        for bookmaster in context["bookmasters"]:
            chapter_count = bookmaster.chaptermasters.count()
            languages = list(
                bookmaster.books.values_list("language__name", flat=True).distinct()
            )
            language_count = len(languages)

            bookmasters_with_info.append(
                {
                    "bookmaster": bookmaster,
                    "chapter_count": chapter_count,
                    "language_count": language_count,
                    "languages": languages,
                }
            )

        context["bookmasters_with_info"] = bookmasters_with_info
        return context


class BookMasterDetailView(LoginRequiredMixin, DetailView):
    model = BookMaster
    template_name = "books/bookmaster/detail.html"
    context_object_name = "bookmaster"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["books"] = self.object.books.all().order_by("language__name")

        # Get all chaptermasters ordered by chapter number
        chaptermasters_queryset = self.object.chaptermasters.all().order_by(
            "chapter_number"
        )

        # Add pagination
        paginator = Paginator(chaptermasters_queryset, 20)
        page_number = self.request.GET.get("page")
        chaptermasters_page = paginator.get_page(page_number)

        context["chaptermasters"] = chaptermasters_page

        # Create chapter status table data for the current page
        languages = [book.language for book in context["books"]]
        chapter_table = []

        for chaptermaster in chaptermasters_page:
            row = {"chaptermaster": chaptermaster, "chapters": {}}

            # Get chapters for this chapter master in each language
            for language in languages:
                try:
                    chapter = chaptermaster.chapters.get(book__language=language)
                    row["chapters"][language.code] = {
                        "chapter": chapter,
                        "status": chapter.get_progress_display(),
                        "status_code": chapter.progress,
                        "is_public": chapter.is_public,
                        "url": (
                            chapter.get_absolute_url()
                            if hasattr(chapter, "get_absolute_url")
                            else None
                        ),
                    }
                except:
                    row["chapters"][language.code] = {
                        "chapter": None,
                        "status": "Not Created",
                        "status_code": "none",
                        "is_public": False,
                        "url": None,
                    }

            chapter_table.append(row)

        context["languages"] = languages
        context["chapter_table"] = chapter_table

        # Add all available languages for translation modal
        context["all_languages"] = Language.objects.all().order_by("name")

        return context


class BookMasterUpdateView(LoginRequiredMixin, UpdateView):
    model = BookMaster
    form_class = BookMasterForm
    template_name = "books/bookmaster/form.html"
    context_object_name = "bookmaster"

    def get_success_url(self):
        return reverse_lazy(
            "books_admin:bookmaster_detail", kwargs={"pk": self.object.pk}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bookmaster"] = self.object
        return context


class BookMasterDeleteView(LoginRequiredMixin, DeleteView):
    model = BookMaster
    template_name = "books/bookmaster/confirm_delete.html"
    context_object_name = "bookmaster"
    success_url = reverse_lazy("books_admin:bookmaster_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bookmaster"] = self.object
        return context


class BatchChapterActionView(LoginRequiredMixin, View):
    """Handle batch operations on chapters within a bookmaster"""

    def post(self, request, bookmaster_pk):
        try:
            # Get the bookmaster and verify ownership
            bookmaster = get_object_or_404(BookMaster, pk=bookmaster_pk)
            if bookmaster.owner != request.user:
                return JsonResponse({"success": False, "message": "Permission denied"})

            # Parse JSON data
            data = json.loads(request.body)
            action = data.get("action")
            chapter_ids = data.get("chapter_ids", [])

            if not action or not chapter_ids:
                return JsonResponse(
                    {"success": False, "message": "Missing required data"}
                )

            # Get the chapter masters
            chaptermasters = ChapterMaster.objects.filter(
                id__in=chapter_ids, bookmaster=bookmaster
            )

            if not chaptermasters.exists():
                return JsonResponse(
                    {"success": False, "message": "No valid chapters found"}
                )

            # Perform the requested action
            result = self._perform_action(action, chaptermasters, data)

            return JsonResponse(result)

        except json.JSONDecodeError:
            return JsonResponse({"success": False, "message": "Invalid JSON data"})
        except Exception as e:
            return JsonResponse(
                {"success": False, "message": f"An error occurred: {str(e)}"}
            )

    def _perform_action(self, action, chaptermasters, data):
        """Perform the batch action on the given chapter masters"""
        success_count = 0
        error_count = 0
        errors = []

        for chaptermaster in chaptermasters:
            try:
                if action == "publish":
                    self._publish_chapters(chaptermaster)
                    success_count += 1
                elif action == "unpublish":
                    self._unpublish_chapters(chaptermaster)
                    success_count += 1
                elif action == "change_status":
                    status = data.get("status")
                    if status in [choice[0] for choice in ChapterProgress.choices]:
                        self._change_status(chaptermaster, status)
                        success_count += 1
                    else:
                        errors.append(
                            f"Invalid status for {chaptermaster.canonical_title}"
                        )
                        error_count += 1
                elif action == "translate":
                    target_language_code = data.get("target_language")
                    if target_language_code:
                        self._create_translation_jobs(
                            chaptermaster, target_language_code
                        )
                        success_count += 1
                    else:
                        errors.append(
                            f"No target language specified for {chaptermaster.canonical_title}"
                        )
                        error_count += 1
                elif action == "delete":
                    self._delete_chaptermaster(chaptermaster)
                    success_count += 1
                else:
                    errors.append(f"Unknown action: {action}")
                    error_count += 1
            except Exception as e:
                errors.append(f"Error with {chaptermaster.canonical_title}: {str(e)}")
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

    def _publish_chapters(self, chaptermaster):
        """Publish all chapters for a chapter master"""
        chapters = Chapter.objects.filter(chaptermaster=chaptermaster)
        for chapter in chapters:
            chapter.publish()

    def _unpublish_chapters(self, chaptermaster):
        """Unpublish all chapters for a chapter master"""
        chapters = Chapter.objects.filter(chaptermaster=chaptermaster)
        for chapter in chapters:
            chapter.unpublish()

    def _change_status(self, chaptermaster, status):
        """Change status for all chapters of a chapter master"""
        chapters = Chapter.objects.filter(chaptermaster=chaptermaster)
        chapters.update(progress=status)

    def _create_translation_jobs(self, chaptermaster, target_language_code):
        """Create translation jobs for chapters in a specific language"""
        target_language = get_object_or_404(Language, code=target_language_code)

        # Get the source chapter from the original language only
        original_language = chaptermaster.bookmaster.original_language
        if not original_language:
            raise ValueError(
                f"BookMaster {chaptermaster.bookmaster.canonical_title} has no original language set"
            )

        # Find the chapter in the original language
        source_chapter = Chapter.objects.filter(
            chaptermaster=chaptermaster, book__language=original_language
        ).first()

        if not source_chapter:
            raise ValueError(
                f"No chapter found in original language ({original_language.name}) for {chaptermaster.canonical_title}"
            )

        jobs_created = 0
        # Check if a translation job already exists for this combination
        existing_job = TranslationJob.objects.filter(
            chapter=source_chapter,
            target_language=target_language,
            status__in=[ProcessingStatus.PENDING, ProcessingStatus.PROCESSING],
        ).first()

        if not existing_job:
            TranslationJob.objects.create(
                chapter=source_chapter,
                target_language=target_language,
                created_by=self.request.user,
            )
            jobs_created += 1

        return jobs_created

    def _delete_chaptermaster(self, chaptermaster):
        """Delete a chapter master and all its chapters"""
        chaptermaster.delete()
