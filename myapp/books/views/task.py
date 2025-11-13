from django.views import View
from django.views.generic import ListView
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse

import logging
import json

from books.models import (
    Chapter,
    TranslationJob,
    AnalysisJob,
    FileUploadJob,
)
from books.choices import ProcessingStatus
from books.tasks import process_translation_jobs

logger = logging.getLogger(__name__)


class TaskListView(LoginRequiredMixin, ListView):
    """
    Unified view for all background tasks (translation, analysis, extraction).

    Shows tasks from TranslationJob, AnalysisJob, and FileUploadJob in a single list.
    Supports filtering by task_type and status, with pagination.
    """
    template_name = "books/tasks/task_list.html"
    context_object_name = "tasks"
    paginate_by = 20

    def get_queryset(self):
        """Aggregate all job types and return unified task list"""
        user = self.request.user

        # Get filter parameters
        task_type_filter = self.request.GET.get('task_type', 'all')
        status_filter = self.request.GET.get('status', 'all')

        # Base querysets - filter by user
        # Note: Use Q objects to include NULL created_by for backwards compatibility
        from django.db.models import Q

        translation_jobs = TranslationJob.objects.filter(
            Q(created_by=user) | Q(created_by__isnull=True)
        ).select_related('chapter', 'chapter__book', 'target_language', 'created_by')

        analysis_jobs = AnalysisJob.objects.filter(
            Q(created_by=user) | Q(created_by__isnull=True)
        ).select_related('chapter', 'chapter__book', 'created_by')

        upload_jobs = FileUploadJob.objects.filter(
            Q(created_by=user) | Q(created_by__isnull=True)
        ).select_related('book', 'book__bookmaster', 'created_by')

        # Apply status filter
        if status_filter != 'all':
            translation_jobs = translation_jobs.filter(status=status_filter)
            analysis_jobs = analysis_jobs.filter(status=status_filter)
            upload_jobs = upload_jobs.filter(status=status_filter)

        # Apply task type filter and combine querysets
        tasks = []

        if task_type_filter in ('all', 'translation'):
            tasks.extend([self._normalize_task(job, 'translation') for job in translation_jobs])

        if task_type_filter in ('all', 'analysis'):
            tasks.extend([self._normalize_task(job, 'analysis') for job in analysis_jobs])

        if task_type_filter in ('all', 'extraction'):
            tasks.extend([self._normalize_task(job, 'extraction') for job in upload_jobs])

        # Sort by created_at descending (newest first)
        tasks.sort(key=lambda x: x['created_at'], reverse=True)

        return tasks

    def _normalize_task(self, job, task_type):
        """
        Normalize different job types into a unified task structure.

        Returns a dict with common fields for template rendering.
        """
        task = {
            'id': job.id,
            'task_type': task_type,
            'status': job.status,
            'status_display': job.get_status_display(),
            'created_at': job.created_at,
            'updated_at': job.updated_at,
            'celery_task_id': job.celery_task_id,
            'error_message': job.error_message,
            'created_by': job.created_by,
            'result_url': None,
            'details': {},
        }

        # Task type specific details
        if task_type == 'translation':
            task['title'] = f"Translate '{job.chapter.title}' to {job.target_language.name}"
            task['details'] = {
                'chapter_title': job.chapter.title,
                'chapter_id': job.chapter.id,
                'target_language': job.target_language.name,
                'book_title': job.chapter.book.title,
            }

            # Get result URL if completed
            if job.status == ProcessingStatus.COMPLETED:
                translated_chapter = Chapter.objects.filter(
                    chaptermaster=job.chapter.chaptermaster,
                    book__language=job.target_language,
                ).first()
                if translated_chapter:
                    task['result_url'] = reverse('books:chapter_detail', kwargs={'pk': translated_chapter.id})

        elif task_type == 'analysis':
            task['title'] = f"Analyze '{job.chapter.title}'"
            task['details'] = {
                'chapter_title': job.chapter.title,
                'chapter_id': job.chapter.id,
                'book_title': job.chapter.book.title,
                'characters_found': job.characters_found,
                'places_found': job.places_found,
                'terms_found': job.terms_found,
                'retry_count': job.retry_count,
            }

            # Get result URL if completed
            if job.status == ProcessingStatus.COMPLETED:
                task['result_url'] = reverse('books:chapter_detail', kwargs={'pk': job.chapter.id})

        elif task_type == 'extraction':
            task['title'] = f"Extract chapters from '{job.book.title}'"
            task['details'] = {
                'book_title': job.book.title,
                'book_id': job.book.id,
                'word_count': job.word_count,
                'character_count': job.character_count,
                'detected_chapters': job.detected_chapter_count,
                'created_chapters': job.created_chapter_count,
            }

            # Get result URL if completed
            if job.status == ProcessingStatus.COMPLETED:
                task['result_url'] = reverse('books:book_detail', kwargs={'pk': job.book.id})

        return task

    def get_context_data(self, **kwargs):
        """Add filter options and task counts to context"""
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Current filters
        context['current_task_type'] = self.request.GET.get('task_type', 'all')
        context['current_status'] = self.request.GET.get('status', 'all')

        # Task type options
        context['task_type_options'] = [
            ('all', 'All Tasks'),
            ('translation', 'Translation'),
            ('analysis', 'Analysis'),
            ('extraction', 'Extraction'),
        ]

        # Status options
        context['status_options'] = [
            ('all', 'All Statuses'),
        ] + [(status[0], status[1]) for status in ProcessingStatus.choices]

        # Task counts by status
        # Note: Include NULL created_by for backwards compatibility with old records
        from django.db.models import Q

        context['task_counts'] = {
            'pending': (
                TranslationJob.objects.filter(
                    Q(created_by=user) | Q(created_by__isnull=True),
                    status=ProcessingStatus.PENDING
                ).count() +
                AnalysisJob.objects.filter(
                    Q(created_by=user) | Q(created_by__isnull=True),
                    status=ProcessingStatus.PENDING
                ).count() +
                FileUploadJob.objects.filter(
                    Q(created_by=user) | Q(created_by__isnull=True),
                    status=ProcessingStatus.PENDING
                ).count()
            ),
            'processing': (
                TranslationJob.objects.filter(
                    Q(created_by=user) | Q(created_by__isnull=True),
                    status=ProcessingStatus.PROCESSING
                ).count() +
                AnalysisJob.objects.filter(
                    Q(created_by=user) | Q(created_by__isnull=True),
                    status=ProcessingStatus.PROCESSING
                ).count() +
                FileUploadJob.objects.filter(
                    Q(created_by=user) | Q(created_by__isnull=True),
                    status=ProcessingStatus.PROCESSING
                ).count()
            ),
            'completed': (
                TranslationJob.objects.filter(
                    Q(created_by=user) | Q(created_by__isnull=True),
                    status=ProcessingStatus.COMPLETED
                ).count() +
                AnalysisJob.objects.filter(
                    Q(created_by=user) | Q(created_by__isnull=True),
                    status=ProcessingStatus.COMPLETED
                ).count() +
                FileUploadJob.objects.filter(
                    Q(created_by=user) | Q(created_by__isnull=True),
                    status=ProcessingStatus.COMPLETED
                ).count()
            ),
            'failed': (
                TranslationJob.objects.filter(
                    Q(created_by=user) | Q(created_by__isnull=True),
                    status=ProcessingStatus.FAILED
                ).count() +
                AnalysisJob.objects.filter(
                    Q(created_by=user) | Q(created_by__isnull=True),
                    status=ProcessingStatus.FAILED
                ).count() +
                FileUploadJob.objects.filter(
                    Q(created_by=user) | Q(created_by__isnull=True),
                    status=ProcessingStatus.FAILED
                ).count()
            ),
        }

        return context


class TaskCountView(LoginRequiredMixin, View):
    """API endpoint to get active task counts for the current user"""

    def get(self, request, *args, **kwargs):
        from django.db.models import Q
        user = request.user

        # Include NULL created_by for backwards compatibility with old records
        pending_count = (
            TranslationJob.objects.filter(
                Q(created_by=user) | Q(created_by__isnull=True),
                status=ProcessingStatus.PENDING
            ).count() +
            AnalysisJob.objects.filter(
                Q(created_by=user) | Q(created_by__isnull=True),
                status=ProcessingStatus.PENDING
            ).count() +
            FileUploadJob.objects.filter(
                Q(created_by=user) | Q(created_by__isnull=True),
                status=ProcessingStatus.PENDING
            ).count()
        )

        processing_count = (
            TranslationJob.objects.filter(
                Q(created_by=user) | Q(created_by__isnull=True),
                status=ProcessingStatus.PROCESSING
            ).count() +
            AnalysisJob.objects.filter(
                Q(created_by=user) | Q(created_by__isnull=True),
                status=ProcessingStatus.PROCESSING
            ).count() +
            FileUploadJob.objects.filter(
                Q(created_by=user) | Q(created_by__isnull=True),
                status=ProcessingStatus.PROCESSING
            ).count()
        )

        return JsonResponse({
            'success': True,
            'pending': pending_count,
            'processing': processing_count,
            'total_active': pending_count + processing_count
        })


class TaskActionView(LoginRequiredMixin, View):
    """Handle task actions: retry, cancel, delete"""

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            task_id = data.get('task_id')
            task_type = data.get('task_type')
            action = data.get('action')

            if not all([task_id, task_type, action]):
                return JsonResponse({
                    'success': False,
                    'message': 'Missing required parameters'
                })

            # Get the job based on type
            job = self._get_job(task_id, task_type, request.user)
            if not job:
                return JsonResponse({
                    'success': False,
                    'message': 'Task not found or access denied'
                })

            # Perform action
            if action == 'retry':
                result = self._retry_task(job, task_type)
            elif action == 'cancel':
                result = self._cancel_task(job, task_type)
            elif action == 'delete':
                result = self._delete_task(job, task_type)
            else:
                return JsonResponse({
                    'success': False,
                    'message': f'Unknown action: {action}'
                })

            return JsonResponse(result)

        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            })
        except Exception as e:
            logger.error(f"Error performing task action: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'An error occurred: {str(e)}'
            })

    def _get_job(self, task_id, task_type, user):
        """Get job instance based on type and verify ownership"""
        try:
            if task_type == 'translation':
                return TranslationJob.objects.get(id=task_id, created_by=user)
            elif task_type == 'analysis':
                return AnalysisJob.objects.get(id=task_id, created_by=user)
            elif task_type == 'extraction':
                return FileUploadJob.objects.get(id=task_id, created_by=user)
        except (TranslationJob.DoesNotExist, AnalysisJob.DoesNotExist, FileUploadJob.DoesNotExist):
            return None

    def _retry_task(self, job, task_type):
        """Retry a failed task"""
        if job.status != ProcessingStatus.FAILED:
            return {
                'success': False,
                'message': 'Only failed tasks can be retried'
            }

        # Reset job status to pending
        job.status = ProcessingStatus.PENDING
        job.error_message = ''
        job.save()

        # Trigger appropriate task
        if task_type == 'translation':
            process_translation_jobs.delay(max_jobs=1)
        elif task_type == 'analysis':
            from books.tasks import analyze_chapter_entities
            analyze_chapter_entities.delay(job.chapter.id, created_by_id=job.created_by_id)
        elif task_type == 'extraction':
            # Note: File extraction retry is complex as we need the original file
            # For now, just reset status - actual retry would need file re-upload
            return {
                'success': False,
                'message': 'File extraction tasks cannot be automatically retried. Please re-upload the file.'
            }

        return {
            'success': True,
            'message': 'Task queued for retry'
        }

    def _cancel_task(self, job, task_type):
        """Cancel a pending task"""
        if job.status not in [ProcessingStatus.PENDING, ProcessingStatus.PROCESSING]:
            return {
                'success': False,
                'message': 'Only pending or processing tasks can be cancelled'
            }

        # Mark as failed with cancellation message
        job.status = ProcessingStatus.FAILED
        job.error_message = 'Cancelled by user'
        job.save()

        # Note: We can't actually stop a running Celery task easily
        # If task is PROCESSING, it will continue but result will be ignored
        if job.status == ProcessingStatus.PROCESSING:
            logger.warning(f"Task {task_type} #{job.id} marked as cancelled but may still be running")

        return {
            'success': True,
            'message': 'Task cancelled successfully'
        }

    def _delete_task(self, job, task_type):
        """Delete a task record"""
        # Only allow deletion of completed or failed tasks
        if job.status in [ProcessingStatus.PENDING, ProcessingStatus.PROCESSING]:
            return {
                'success': False,
                'message': 'Cannot delete pending or processing tasks. Cancel them first.'
            }

        job.delete()

        return {
            'success': True,
            'message': 'Task deleted successfully'
        }
