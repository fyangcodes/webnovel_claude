"""
Celery tasks for AI-powered chapter analysis.

These tasks handle:
- Entity extraction and summarization for chapters
- Async processing of chapter context analysis
"""

from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def analyze_chapter_entities(self, chapter_id):
    """
    Async task to analyze chapter entities and summary using AI.

    This task is queued separately from file uploads to avoid blocking.
    It can be retried on failure and runs in parallel for multiple chapters.

    Args:
        chapter_id: Chapter primary key

    Returns:
        dict: Analysis result with status and entity counts
    """
    from books.models import Chapter, ChapterContext, AnalysisJob
    from books.choices import ProcessingStatus

    # Get or create the analysis job
    job = None
    try:
        chapter = Chapter.objects.select_related(
            'book',
            'book__language',
            'book__bookmaster'
        ).get(id=chapter_id)

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
                job.save()
            else:
                # PENDING or PROCESSING - update it
                logger.info(f"Updating existing job {existing_job.id} for chapter {chapter_id}")
                job = existing_job
                job.status = ProcessingStatus.PROCESSING
                job.celery_task_id = self.request.id
                job.retry_count = self.request.retries
                job.save()
        else:
            # Create new job
            logger.info(f"Creating new analysis job for chapter {chapter_id}")
            job = AnalysisJob.objects.create(
                chapter=chapter,
                status=ProcessingStatus.PROCESSING,
                celery_task_id=self.request.id,
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
