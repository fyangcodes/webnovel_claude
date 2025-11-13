"""
Celery tasks for file upload and text extraction.

These tasks handle:
- Processing uploaded files asynchronously
- Extracting text and chapters from files
- Creating chapter records in the database
- Batch processing with concurrency control
"""

from celery import shared_task
from django.db import transaction, models
from django.core.files.uploadedfile import InMemoryUploadedFile
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_file_upload(self, job_id, file_content, filename):
    """
    Process uploaded file and create chapters asynchronously.

    Args:
        job_id: FileUploadJob primary key
        file_content: File content as bytes
        filename: Original filename

    Returns:
        dict: Processing result with status and counts
    """
    from books.models import FileUploadJob
    from books.choices import ProcessingStatus
    from books.utils import TextExtractor

    try:
        # Get the job
        job = FileUploadJob.objects.select_related('book', 'book__bookmaster').get(id=job_id)

        # Mark as processing
        job.status = ProcessingStatus.PROCESSING
        job.save(update_fields=['status', 'updated_at'])

        # Create file-like object from bytes
        file_obj = BytesIO(file_content)
        uploaded_file = InMemoryUploadedFile(
            file_obj,
            field_name='file',
            name=filename,
            content_type='text/plain',
            size=len(file_content),
            charset='utf-8'
        )

        # Extract text and chapters using the utility function
        result = TextExtractor.extract_text_from_file(
            uploaded_file,
            include_chapters=True
        )

        # Update job with extraction results
        job.word_count = result.get('word_count', 0)
        job.character_count = result.get('character_count', 0)
        job.detected_chapter_count = result.get('chapter_count', 0)

        created_count = 0

        if job.auto_create_chapters and result.get('chapters'):
            created_count = _create_chapters_from_upload(
                job.book,
                result['chapters'],
                created_by_id=job.created_by_id if job.created_by else None
            )

        job.created_chapter_count = created_count
        job.status = ProcessingStatus.COMPLETED
        job.error_message = ""
        job.save()

        logger.info(
            f"File upload job {job_id} completed: "
            f"{created_count} chapters created from {result.get('chapter_count', 0)} detected"
        )

        return {
            'job_id': job_id,
            'status': 'completed',
            'created_chapters': created_count,
            'detected_chapters': result.get('chapter_count', 0),
        }

    except FileUploadJob.DoesNotExist:
        logger.error(f"FileUploadJob {job_id} not found")
        return {'job_id': job_id, 'status': 'failed', 'error': 'Job not found'}

    except Exception as e:
        logger.error(f"Error processing file upload job {job_id}: {str(e)}", exc_info=True)
        try:
            job = FileUploadJob.objects.get(id=job_id)
            job.status = ProcessingStatus.FAILED
            job.error_message = str(e)
            job.save()
        except FileUploadJob.DoesNotExist:
            pass

        return {'job_id': job_id, 'status': 'failed', 'error': str(e)}


@transaction.atomic
def _create_chapters_from_upload(book, chapters_data, created_by_id=None):
    """
    Create chapters and chapter masters from extracted data.
    Helper function for process_file_upload task.

    Note: This creates chapters WITHOUT triggering AI entity extraction
    to avoid blocking. AI extraction jobs are created for batch processing.

    Args:
        book: Book instance to create chapters for
        chapters_data: List of chapter dictionaries with title and content
        created_by_id: User ID who created the upload job (optional)

    Returns:
        int: Number of chapters created
    """
    from books.models import ChapterMaster, Chapter, AnalysisJob
    from books.choices import ChapterProgress, ProcessingStatus

    # Get the highest existing chapter number for this bookmaster
    existing_max_number = (
        ChapterMaster.objects.filter(bookmaster=book.bookmaster).aggregate(
            max_number=models.Max("chapter_number")
        )["max_number"]
        or 0
    )

    created_chapters = 0
    created_chapter_ids = []

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
                created_chapter_ids.append(chapter.id)

        except Exception as e:
            logger.error(f"Error creating chapter {i}: {str(e)}")
            continue

    # Update book metadata after all chapters are created
    book.update_metadata()

    # Create AI analysis jobs for original language chapters
    # Jobs will be processed by the batch processor with concurrency control
    if book.language == book.bookmaster.original_language and created_chapter_ids:
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Get the user instance if ID provided
        created_by = None
        if created_by_id:
            try:
                created_by = User.objects.get(id=created_by_id)
            except User.DoesNotExist:
                logger.warning(f"User {created_by_id} not found for analysis jobs")

        # Create analysis jobs for all new chapters
        for chapter_id in created_chapter_ids:
            try:
                chapter = Chapter.objects.get(id=chapter_id)
                # Create job with PENDING status - batch processor will pick it up
                AnalysisJob.objects.create(
                    chapter=chapter,
                    status=ProcessingStatus.PENDING,
                    created_by=created_by,
                )
            except Chapter.DoesNotExist:
                logger.error(f"Chapter {chapter_id} not found when creating analysis job")

        logger.info(f"Created {len(created_chapter_ids)} analysis jobs for batch processing")

    return created_chapters


@shared_task(bind=True)
def process_extraction_jobs(self, max_jobs=None):
    """
    Process pending file upload/extraction jobs in batch with concurrency protection.

    Uses both individual (extraction=3) and global limits to control concurrency.
    Extraction jobs can run in parallel up to the configured limit.

    Args:
        max_jobs: Maximum number of jobs to process in this batch.
                 If None, uses available slots from concurrency manager.

    Returns:
        int: Number of jobs processed
    """
    from books.models import FileUploadJob
    from books.choices import ProcessingStatus
    from books.utils import JobConcurrencyManager

    concurrency_manager = JobConcurrencyManager()
    processed_count = 0
    failed_count = 0

    # Determine actual max_jobs based on available slots
    if max_jobs is None:
        max_jobs = concurrency_manager.get_available_slots('extraction')
    else:
        # Respect both the provided limit and available slots
        available_slots = concurrency_manager.get_available_slots('extraction')
        max_jobs = min(max_jobs, available_slots)

    if max_jobs == 0:
        logger.info("No extraction slots available (global or type limit reached)")
        return 0

    logger.info(f"Processing up to {max_jobs} extraction jobs")

    while processed_count < max_jobs:
        # Claim a job atomically
        with transaction.atomic():
            # Get the oldest pending job
            pending_job = (
                FileUploadJob.objects.filter(status=ProcessingStatus.PENDING)
                .select_related('book', 'book__bookmaster')
                .order_by("created_at")
                .first()
            )

            if not pending_job:
                logger.info("No pending extraction jobs found")
                break

            # Try to claim this specific job atomically
            updated_count = FileUploadJob.objects.filter(
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
        # Note: We cannot call process_file_upload as it expects file_content
        # This batch processor is for future use when jobs store file references
        try:
            with concurrency_manager.acquire_slot('extraction'):
                logger.warning(
                    f"Extraction job {job.id} found but cannot process "
                    f"(file content not stored in job record)"
                )
                # For now, mark as failed - extraction jobs need file content
                job.status = ProcessingStatus.FAILED
                job.error_message = "Batch processing not supported - file content not stored"
                job.save()
                failed_count += 1
                processed_count += 1

        except ValueError as e:
            # Slot acquisition failed - shouldn't happen due to pre-check
            logger.error(f"Failed to acquire extraction slot: {e}")
            job.status = ProcessingStatus.PENDING
            job.save()
            break

        except Exception as e:
            logger.error(f"Unexpected error processing extraction job {job.id}: {e}", exc_info=True)
            job.status = ProcessingStatus.FAILED
            job.error_message = f"Unexpected error: {str(e)}"
            job.save()
            failed_count += 1
            processed_count += 1

    if processed_count == 0:
        print("No extraction jobs were processed")
    else:
        print(f"Processed {processed_count} extraction jobs ({failed_count} failed)")

    return processed_count
