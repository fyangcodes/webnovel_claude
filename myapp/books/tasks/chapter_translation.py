"""
Celery tasks for chapter translation.

These tasks handle:
- Processing translation jobs in batches
- Individual chapter translation
"""

from celery import shared_task
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_translation_jobs(self, max_jobs):
    """
    Process pending translation jobs with concurrency protection.

    Args:
        max_jobs: Maximum number of jobs to process in this batch

    Returns:
        int: Number of jobs processed
    """
    from books.models import TranslationJob
    from books.choices import ProcessingStatus
    from books.utils import (
        ChapterTranslationService,
        TranslationValidationError,
        RateLimitError,
        TranslationAPIError,
        TranslationError,
    )

    service = ChapterTranslationService()
    processed_count = 0

    while processed_count < max_jobs:
        # SQLite doesn't support row locking, use single job claiming
        with transaction.atomic():
            # Get the oldest pending job
            pending_job = (
                TranslationJob.objects.filter(status=ProcessingStatus.PENDING)
                .order_by("created_at")
                .first()
            )

            if not pending_job:
                logger.info("No pending translation jobs found")
                break

            # Try to claim this specific job atomically
            updated_count = TranslationJob.objects.filter(
                id=pending_job.id,
                status=ProcessingStatus.PENDING,  # Double-check status
            ).update(status=ProcessingStatus.PROCESSING)

            if updated_count == 0:
                # Job was claimed by another process, try next iteration
                logger.info("Job was claimed by another process, retrying")
                continue

            job = pending_job
            job.status = ProcessingStatus.PROCESSING  # Update local object
            job.celery_task_id = self.request.id  # Store Celery task ID
            job.save(update_fields=["status", "celery_task_id"])

        # Process the job outside the transaction to avoid long locks
        try:
            logger.info(f"Starting translation of {job.chapter.title}")

            service.translate_chapter(job.chapter, job.target_language.code)

            # Update job status
            job.status = ProcessingStatus.COMPLETED
            job.error_message = ""  # Clear any previous error
            job.save()

            print(
                f"✓ Translated chapter '{job.chapter.title}' to {job.target_language.name}"
            )
            processed_count += 1

        except TranslationValidationError as e:
            job.status = ProcessingStatus.FAILED
            job.error_message = f"Validation error: {str(e)}"
            job.save()
            logger.error(f"Validation failed for job {job.id}: {e}")
            print(f"✗ Validation failed: {e}")
            processed_count += 1

        except RateLimitError as e:
            # Don't mark as failed for rate limits, leave as processing to retry later
            job.status = ProcessingStatus.PENDING
            job.error_message = f"Rate limit: {str(e)}"
            job.save()
            logger.warning(f"Rate limit hit for job {job.id}, will retry later")
            print(f"⏸ Rate limit reached, stopping batch processing")
            break

        except (TranslationAPIError, TranslationError) as e:
            job.status = ProcessingStatus.FAILED
            job.error_message = str(e)
            job.save()
            logger.error(f"Translation failed for job {job.id}: {e}")
            print(f"✗ Translation failed: {e}")
            processed_count += 1

        except Exception as e:
            # Catch any unexpected errors
            job.status = ProcessingStatus.FAILED
            job.error_message = f"Unexpected error: {str(e)}"
            job.save()
            logger.error(f"Unexpected error for job {job.id}: {e}", exc_info=True)
            print(f"✗ Unexpected error: {e}")
            processed_count += 1

    if processed_count == 0:
        print("No translation jobs were processed")
    else:
        print(f"Processed {processed_count} translation jobs")

    return processed_count
