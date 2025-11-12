"""
Celery tasks for file upload and text extraction.

These tasks handle:
- Processing uploaded files asynchronously
- Extracting text and chapters from files
- Creating chapter records in the database
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
                result['chapters']
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
def _create_chapters_from_upload(book, chapters_data):
    """
    Create chapters and chapter masters from extracted data.
    Helper function for process_file_upload task.

    Note: This creates chapters WITHOUT triggering AI entity extraction
    to avoid blocking. AI extraction is queued as separate async tasks.

    Args:
        book: Book instance to create chapters for
        chapters_data: List of chapter dictionaries with title and content

    Returns:
        int: Number of chapters created
    """
    from books.models import ChapterMaster, Chapter
    from books.choices import ChapterProgress
    from books.tasks.chapter_analysis import analyze_chapter_entities

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

    # Queue AI entity extraction tasks for original language chapters
    if book.language == book.bookmaster.original_language:
        for chapter_id in created_chapter_ids:
            # Queue each chapter's AI analysis as a separate task
            # This runs in parallel and doesn't block the upload job
            analyze_chapter_entities.delay(chapter_id)

    return created_chapters
