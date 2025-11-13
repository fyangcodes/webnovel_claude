"""
Celery tasks for AI-powered chapter analysis.

These tasks handle:
- Entity extraction and summarization for chapters
- Async processing of chapter context analysis
- Batch processing with concurrency control
"""

from celery import shared_task
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def analyze_chapter_entities(self, chapter_id, created_by_id=None):
    """
    Async task to analyze chapter entities and summary using AI.

    This task is queued separately from file uploads to avoid blocking.
    It can be retried on failure and runs in parallel for multiple chapters.

    Args:
        chapter_id: Chapter primary key
        created_by_id: User ID who created the chapter (optional)

    Returns:
        dict: Analysis result with status and entity counts
    """
    from books.models import Chapter, ChapterContext, AnalysisJob
    from books.choices import ProcessingStatus
    from django.contrib.auth import get_user_model

    User = get_user_model()

    # Get or create the analysis job
    job = None
    try:
        chapter = Chapter.objects.select_related(
            'book',
            'book__language',
            'book__bookmaster'
        ).get(id=chapter_id)

        # Determine the user who should be set as created_by
        created_by = None
        if created_by_id:
            try:
                created_by = User.objects.get(id=created_by_id)
            except User.DoesNotExist:
                logger.warning(f"User {created_by_id} not found for analysis job")

        # Check if any job already exists for this chapter
        existing_job = AnalysisJob.objects.filter(chapter=chapter).first()

        if existing_job:
            # Job already exists - check if it's completed
            if existing_job.status == ProcessingStatus.COMPLETED:
                logger.info(f"Analysis job for chapter {chapter_id} already completed, skipping")
                return {
                    'chapter_id': chapter_id,
                    'status': 'already_completed',
                    'entities_found': {
                        'characters': existing_job.characters_found,
                        'places': existing_job.places_found,
                        'terms': existing_job.terms_found,
                    }
                }
            elif existing_job.status == ProcessingStatus.FAILED:
                # Retry failed job
                logger.info(f"Retrying failed analysis job {existing_job.id} for chapter {chapter_id}")
                job = existing_job
                job.status = ProcessingStatus.PROCESSING
                job.celery_task_id = self.request.id
                job.retry_count = self.request.retries
                job.error_message = ""
                # Update created_by if provided and not already set
                if created_by and not job.created_by:
                    job.created_by = created_by
                job.save()
            else:
                # PENDING or PROCESSING - update it
                logger.info(f"Updating existing job {existing_job.id} for chapter {chapter_id}")
                job = existing_job
                job.status = ProcessingStatus.PROCESSING
                job.celery_task_id = self.request.id
                job.retry_count = self.request.retries
                # Update created_by if provided and not already set
                if created_by and not job.created_by:
                    job.created_by = created_by
                job.save()
        else:
            # Create new job
            logger.info(f"Creating new analysis job for chapter {chapter_id}")
            job = AnalysisJob.objects.create(
                chapter=chapter,
                status=ProcessingStatus.PROCESSING,
                celery_task_id=self.request.id,
                created_by=created_by,
            )

        # Only analyze if this is an original language chapter
        if chapter.book.language != chapter.book.bookmaster.original_language:
            logger.info(f"Skipping AI analysis for translated chapter {chapter_id}")
            job.status = ProcessingStatus.COMPLETED
            job.error_message = "Skipped: Not original language chapter"
            job.save()
            return {'chapter_id': chapter_id, 'status': 'skipped', 'reason': 'not_original_language'}

        # Create or get ChapterContext
        context, created = ChapterContext.objects.get_or_create(chapter=chapter)

        # Skip if already analyzed (unless forced)
        if not created and context.key_terms and context.summary:
            logger.info(f"Chapter {chapter_id} already has AI analysis, skipping")
            job.status = ProcessingStatus.COMPLETED
            job.save()
            return {'chapter_id': chapter_id, 'status': 'already_analyzed'}

        # Perform AI analysis
        logger.info(f"Starting AI entity extraction for chapter {chapter_id}")
        result = context.analyze_chapter()

        # Update job with results
        job.characters_found = len(result.get('characters', []))
        job.places_found = len(result.get('places', []))
        job.terms_found = len(result.get('terms', []))
        job.status = ProcessingStatus.COMPLETED
        job.error_message = ""
        job.save()

        logger.info(
            f"AI analysis completed for chapter {chapter_id}: "
            f"{job.characters_found} characters, "
            f"{job.places_found} places, "
            f"{job.terms_found} terms"
        )

        return {
            'chapter_id': chapter_id,
            'status': 'completed',
            'entities_found': {
                'characters': job.characters_found,
                'places': job.places_found,
                'terms': job.terms_found,
            }
        }

    except Chapter.DoesNotExist:
        logger.error(f"Chapter {chapter_id} not found for AI analysis")
        if job:
            job.status = ProcessingStatus.FAILED
            job.error_message = "Chapter not found"
            job.save()
        return {'chapter_id': chapter_id, 'status': 'failed', 'error': 'Chapter not found'}

    except Exception as e:
        logger.error(f"Error analyzing chapter {chapter_id}: {str(e)}", exc_info=True)

        # Update job with error
        if job:
            job.retry_count = self.request.retries + 1
            job.error_message = str(e)
            job.save()

        # Retry with exponential backoff
        try:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for chapter {chapter_id} AI analysis")
            if job:
                job.status = ProcessingStatus.FAILED
                job.save()
            return {'chapter_id': chapter_id, 'status': 'failed', 'error': str(e)}


@shared_task(bind=True)
def process_analysis_jobs(self, max_jobs=None):
    """
    Process pending analysis jobs in batch with concurrency protection.

    Uses both individual (analysis=3) and global limits to control concurrency.
    Analysis jobs can run in parallel up to the configured limit.

    Args:
        max_jobs: Maximum number of jobs to process in this batch.
                 If None, uses available slots from concurrency manager.

    Returns:
        int: Number of jobs processed
    """
    from books.models import AnalysisJob
    from books.choices import ProcessingStatus
    from books.utils import JobConcurrencyManager

    concurrency_manager = JobConcurrencyManager()
    processed_count = 0
    failed_count = 0

    # Determine how many jobs to process
    # If max_jobs is None, process all pending jobs (respecting concurrency limits per job)
    # If max_jobs is specified, stop after processing that many
    process_all = max_jobs is None
    if process_all:
        max_jobs = float('inf')  # Process until queue is empty

    logger.info(
        f"Processing {'all pending' if process_all else f'up to {max_jobs}'} analysis jobs"
    )

    while processed_count < max_jobs:
        # Check if we can acquire a slot before claiming a job
        if not concurrency_manager.can_acquire_slot('analysis'):
            logger.info(
                "No analysis slots available (global or type limit reached). "
                f"Processed {processed_count} jobs so far."
            )
            break
        # Claim a job atomically
        with transaction.atomic():
            # Get the oldest pending job
            pending_job = (
                AnalysisJob.objects.filter(status=ProcessingStatus.PENDING)
                .select_related('chapter', 'chapter__book')
                .order_by("created_at")
                .first()
            )

            if not pending_job:
                logger.info("No pending analysis jobs found")
                break

            # Try to claim this specific job atomically
            updated_count = AnalysisJob.objects.filter(
                id=pending_job.id,
                status=ProcessingStatus.PENDING,
            ).update(status=ProcessingStatus.PROCESSING)

            if updated_count == 0:
                # Job was claimed by another process, try next iteration
                logger.info("Job was claimed by another process, retrying")
                continue

            job = pending_job
            job.status = ProcessingStatus.PROCESSING
            job.celery_task_id = self.request.id
            job.save(update_fields=["status", "celery_task_id"])

        # Process the job outside the transaction with concurrency tracking
        try:
            with concurrency_manager.acquire_slot('analysis'):
                logger.info(f"Starting analysis of chapter {job.chapter.id}: {job.chapter.title}")

                # Call the actual analysis task logic synchronously
                result = analyze_chapter_entities(job.chapter.id, job.created_by_id)

                if result.get('status') == 'completed':
                    print(f"✓ Analyzed chapter '{job.chapter.title}'")
                    processed_count += 1
                elif result.get('status') == 'failed':
                    print(f"✗ Analysis failed for '{job.chapter.title}': {result.get('error')}")
                    failed_count += 1
                    processed_count += 1
                else:
                    # Skipped or already completed
                    processed_count += 1

        except ValueError as e:
            # Slot acquisition failed - shouldn't happen due to pre-check
            logger.error(f"Failed to acquire analysis slot: {e}")
            job.status = ProcessingStatus.PENDING
            job.save()
            break

        except Exception as e:
            logger.error(f"Unexpected error processing analysis job {job.id}: {e}", exc_info=True)
            job.status = ProcessingStatus.FAILED
            job.error_message = f"Unexpected error: {str(e)}"
            job.save()
            failed_count += 1
            processed_count += 1

    if processed_count == 0:
        print("No analysis jobs were processed")
    else:
        print(f"Processed {processed_count} analysis jobs ({failed_count} failed)")

    return processed_count
