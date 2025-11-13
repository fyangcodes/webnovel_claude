from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse

import logging
import json

from books.models import (
    Book,
    Chapter,
    Language,
    TranslationJob,
    BookMaster,
    ChapterMaster,
)
from books.choices import ProcessingStatus, ChapterProgress
from books.tasks import process_translation_jobs

logger = logging.getLogger(__name__)


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

            # Trigger Celery task to process pending jobs (will process sequentially)
            # Don't pass max_jobs - let it process all available slots
            process_translation_jobs.delay()

            return JsonResponse(
                {
                    "success": True,
                    "job_id": translation_job.id,
                    "message": f"Translation to {target_language.name} has been queued. You'll be notified when it's complete.",
                    "status_url": reverse("books:task_status")
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


class BatchActionView(LoginRequiredMixin, View):
    """Generalized batch action view for chapters and chapter masters"""

    def post(self, request, **kwargs):
        try:
            # Determine the model type from the URL or POST data
            model_type = self._get_model_type(**kwargs)

            # Get the parent object and verify ownership
            parent_object = self._get_parent_object(model_type, **kwargs)
            if not self._check_ownership(parent_object, request.user):
                return JsonResponse({"success": False, "message": "Permission denied"})

            # Parse JSON data
            data = json.loads(request.body)
            action = data.get("action")
            item_ids = data.get(
                "chapter_ids", []
            )  # Keep "chapter_ids" for backward compatibility

            if not action or not item_ids:
                return JsonResponse(
                    {"success": False, "message": "Missing required data"}
                )

            # Get the items to act upon
            items = self._get_items(model_type, parent_object, item_ids)

            if not items.exists():
                return JsonResponse(
                    {"success": False, "message": "No valid items found"}
                )

            # Perform the requested action
            result = self._perform_action(action, items, data, model_type)

            return JsonResponse(result)

        except json.JSONDecodeError:
            return JsonResponse({"success": False, "message": "Invalid JSON data"})
        except Exception as e:
            return JsonResponse(
                {"success": False, "message": f"An error occurred: {str(e)}"}
            )

    def _get_model_type(self, **kwargs):
        """Determine model type from URL parameters"""
        if "bookmaster_pk" in kwargs:
            return "chaptermaster"
        elif "book_pk" in kwargs:
            return "chapter"
        else:
            raise ValueError("Unable to determine model type from URL parameters")

    def _get_parent_object(self, model_type, **kwargs):
        """Get the parent object (BookMaster or Book)"""
        if model_type == "chaptermaster":
            return get_object_or_404(BookMaster, pk=kwargs["bookmaster_pk"])
        elif model_type == "chapter":
            return get_object_or_404(Book, pk=kwargs["book_pk"])

    def _check_ownership(self, parent_object, user):
        """Check if user owns the parent object"""
        if hasattr(parent_object, "owner"):
            return parent_object.owner == user
        elif hasattr(parent_object, "bookmaster"):
            return parent_object.bookmaster.owner == user
        return False

    def _get_items(self, model_type, parent_object, item_ids):
        """Get the items to perform actions on"""
        if model_type == "chaptermaster":
            return ChapterMaster.objects.filter(
                id__in=item_ids, bookmaster=parent_object
            )
        elif model_type == "chapter":
            return Chapter.objects.filter(id__in=item_ids, book=parent_object)

    def _perform_action(self, action, items, data, model_type):
        """Perform the batch action on the given items"""
        success_count = 0
        error_count = 0
        errors = []

        for item in items:
            try:
                if action == "publish":
                    self._publish_item(item, model_type)
                    success_count += 1
                elif action == "unpublish":
                    self._unpublish_item(item, model_type)
                    success_count += 1
                elif action == "change_status":
                    status = data.get("status")
                    if status in [choice[0] for choice in ChapterProgress.choices]:
                        self._change_status(item, status, model_type)
                        success_count += 1
                    else:
                        item_title = self._get_item_title(item, model_type)
                        errors.append(f"Invalid status for {item_title}")
                        error_count += 1
                elif action == "translate":
                    target_language_code = data.get("target_language")
                    if target_language_code:
                        self._create_translation_jobs(
                            item, target_language_code, model_type
                        )
                        success_count += 1
                    else:
                        item_title = self._get_item_title(item, model_type)
                        errors.append(f"No target language specified for {item_title}")
                        error_count += 1
                elif action == "delete":
                    self._delete_item(item, model_type)
                    success_count += 1
                else:
                    errors.append(f"Unknown action: {action}")
                    error_count += 1
            except Exception as e:
                item_title = self._get_item_title(item, model_type)
                errors.append(f"Error with {item_title}: {str(e)}")
                error_count += 1

        # Prepare response message
        item_name = (
            "chapter master(s)" if model_type == "chaptermaster" else "chapter(s)"
        )

        if success_count > 0 and error_count == 0:
            message = f"Successfully processed {success_count} {item_name}"
        elif success_count > 0 and error_count > 0:
            message = f"Processed {success_count} {item_name} successfully, {error_count} failed"
        else:
            message = f"Failed to process {item_name}: {'; '.join(errors[:3])}"
            if len(errors) > 3:
                message += f" (and {len(errors) - 3} more errors)"

        return {
            "success": success_count > 0,
            "message": message,
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,
        }

    def _get_item_title(self, item, model_type):
        """Get the title of an item"""
        if model_type == "chaptermaster":
            return item.canonical_title
        else:
            return item.title

    def _publish_item(self, item, model_type):
        """Publish an item"""
        if model_type == "chaptermaster":
            chapters = Chapter.objects.filter(chaptermaster=item)
            for chapter in chapters:
                chapter.publish()
        else:
            item.publish()

    def _unpublish_item(self, item, model_type):
        """Unpublish an item"""
        if model_type == "chaptermaster":
            chapters = Chapter.objects.filter(chaptermaster=item)
            for chapter in chapters:
                chapter.unpublish()
        else:
            item.unpublish()

    def _change_status(self, item, status, model_type):
        """Change status of an item"""
        if model_type == "chaptermaster":
            chapters = Chapter.objects.filter(chaptermaster=item)
            chapters.update(progress=status)
        else:
            item.progress = status
            item.save()

    def _create_translation_jobs(self, item, target_language_code, model_type):
        """Create translation jobs for an item"""
        target_language = get_object_or_404(Language, code=target_language_code)
        job_created = False

        if model_type == "chaptermaster":
            # Get the source chapter from the original language only
            original_language = item.bookmaster.original_language
            if not original_language:
                raise ValueError(
                    f"BookMaster {item.bookmaster.canonical_title} has no original language set"
                )

            # Find the chapter in the original language
            source_chapter = Chapter.objects.filter(
                chaptermaster=item, book__language=original_language
            ).first()

            if not source_chapter:
                raise ValueError(
                    f"No chapter found in original language ({original_language.name}) for {item.canonical_title}"
                )

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
                job_created = True
        else:
            # Direct chapter - find source chapter from original language
            original_language = item.chaptermaster.bookmaster.original_language
            if not original_language:
                raise ValueError(
                    f"BookMaster {item.chaptermaster.bookmaster.canonical_title} has no original language set"
                )

            # Find the chapter in the original language for this chaptermaster
            source_chapter = Chapter.objects.filter(
                chaptermaster=item.chaptermaster, book__language=original_language
            ).first()

            if not source_chapter:
                raise ValueError(
                    f"No chapter found in original language ({original_language.name}) for {item.chaptermaster.canonical_title}"
                )

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
                job_created = True

        # Trigger Celery task if a new job was created
        if job_created:
            # Don't pass max_jobs - let it process all available slots
            process_translation_jobs.delay()

    def _delete_item(self, item, model_type):
        """Delete an item"""
        item.delete()
