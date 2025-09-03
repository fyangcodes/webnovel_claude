from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

import logging

from books.models import Book, Chapter, Language, TranslationJob
from books.choices import ProcessingStatus
from translation.services import (
    TranslationService,
    ValidationError as TranslationValidationError,
    APIError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class TaskStatusView(LoginRequiredMixin, View):
    """Check status of background tasks like translations"""

    def get(self, request, *args, **kwargs):
        task_id = request.GET.get("task_id")
        task_type = request.GET.get("task_type", "unknown")

        if not task_id:
            return JsonResponse({"success": False, "error": "Task ID is required"})

        if task_type == "translation":
            try:
                job = get_object_or_404(
                    TranslationJob, id=task_id, created_by=request.user
                )

                is_pending = job.status == ProcessingStatus.PENDING
                is_processing = job.status == ProcessingStatus.PROCESSING
                is_success = job.status == ProcessingStatus.COMPLETED
                is_failure = job.status == ProcessingStatus.FAILED

                response_data = {
                    "success": True,
                    "task_id": task_id,
                    "task_type": task_type,
                    "status": job.get_status_display(),
                    "is_pending": is_pending,
                    "is_processing": is_processing,
                    "is_success": is_success,
                    "is_failure": is_failure,
                }

                if is_success:
                    # Find the translated chapter
                    translated_chapter = Chapter.objects.filter(
                        chaptermaster=job.chapter.chaptermaster,
                        book__language=job.target_language,
                    ).first()

                    if translated_chapter:
                        response_data["redirect_url"] = reverse(
                            "books_admin:chapter_detail",
                            kwargs={"pk": translated_chapter.id},
                        )
                        response_data["message"] = (
                            f"Translation to {job.target_language.name} completed successfully!"
                        )
                    else:
                        response_data["message"] = (
                            "Translation completed but chapter not found."
                        )

                elif is_failure:
                    response_data["message"] = job.error_message or "Translation failed"

                elif is_processing:
                    response_data["message"] = (
                        f"Translating to {job.target_language.name}..."
                    )

                else:  # pending
                    response_data["message"] = (
                        f"Translation to {job.target_language.name} is queued"
                    )

                return JsonResponse(response_data)

            except TranslationJob.DoesNotExist:
                return JsonResponse(
                    {"success": False, "error": "Translation job not found"}
                )

        # Default response for unknown task types
        return JsonResponse(
            {"success": False, "error": f"Unknown task type: {task_type}"}
        )


class ChapterTranslationView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        chapter_id = kwargs.get("chapter_id")
        target_language_code = kwargs.get("language_code")
        chapter = get_object_or_404(
            Chapter, pk=chapter_id, book__bookmaster__owner=request.user
        )

        try:
            # Get target language
            target_language = get_object_or_404(Language, code=target_language_code)

            # Check if translation job already exists
            existing_job = TranslationJob.objects.filter(
                chapter=chapter,
                target_language=target_language,
                status__in=[ProcessingStatus.PENDING, ProcessingStatus.PROCESSING],
            ).first()

            if existing_job:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Translation job already in progress for this language.",
                    }
                )

            # Check if translation already exists
            if Chapter.objects.filter(
                chaptermaster=chapter.chaptermaster, book__language=target_language
            ).exists():
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Translation already exists for this language.",
                    }
                )

            # Create translation job for background processing
            translation_job = TranslationJob.objects.create(
                chapter=chapter,
                target_language=target_language,
                created_by=request.user,
                status=ProcessingStatus.PENDING,
            )

            return JsonResponse(
                {
                    "success": True,
                    "job_id": translation_job.id,
                    "message": f"Translation to {target_language.name} has been queued. You'll be notified when it's complete.",
                    "status_url": reverse("books_admin:task_status")
                    + f"?task_id={translation_job.id}&task_type=translation",
                }
            )

        except Language.DoesNotExist:
            return JsonResponse(
                {
                    "success": False,
                    "error": f"Target language '{target_language_code}' not found.",
                }
            )

        except Exception as e:
            logger.error(f"Error creating translation job: {str(e)}")
            return JsonResponse(
                {"success": False, "error": f"Failed to queue translation: {str(e)}"}
            )
