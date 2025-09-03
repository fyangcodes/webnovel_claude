"""
OpenAI translation service with improved error handling and validation
"""

import logging
import time
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from openai import OpenAI

from books.models import Chapter, Language, TranslationJob
from books.choices import ProcessingStatus

logger = logging.getLogger("translation")


class TranslationError(Exception):
    """Base exception for translation errors"""

    pass


class ValidationError(TranslationError):
    """Validation error for translation input"""

    pass


class APIError(TranslationError):
    """OpenAI API related error"""

    pass


class RateLimitError(TranslationError):
    """Rate limit exceeded error"""

    pass


class TranslationService:
    """Improved translation service with validation and error handling"""

    # Content validation limits
    MAX_CONTENT_LENGTH = 8000  # Conservative limit for token estimation
    MIN_CONTENT_LENGTH = 10
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds

    def __init__(self):
        self._validate_settings()
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.TRANSLATION_MODEL
        self.max_tokens = settings.TRANSLATION_MAX_TOKENS
        self.temperature = settings.TRANSLATION_TEMPERATURE
        self._last_request_time = 0
        self._min_request_interval = 1  # Minimum 1 second between requests

    def _validate_settings(self):
        """Validate required settings are present"""
        required_settings = [
            "OPENAI_API_KEY",
            "TRANSLATION_MODEL",
            "TRANSLATION_MAX_TOKENS",
            "TRANSLATION_TEMPERATURE",
        ]

        missing_settings = []
        for setting in required_settings:
            if not hasattr(settings, setting) or not getattr(settings, setting):
                missing_settings.append(setting)

        if missing_settings:
            raise ValidationError(
                f"Missing required settings: {', '.join(missing_settings)}"
            )

    def translate_chapter(
        self, source_chapter: Chapter, target_language_code: str
    ) -> Chapter:
        """Translate a chapter to target language with validation and error handling"""
        try:
            # Validate input
            self._validate_chapter_content(source_chapter)
            target_language = self._get_target_language(target_language_code)

            # Rate limiting
            self._enforce_rate_limit()

            # Create prompt for translation (title + content)
            prompt = self._build_translation_prompt(
                source_chapter.title,
                source_chapter.content,
                source_chapter.book.language.name,
                target_language.name,
            )

            # Call OpenAI API with retry logic
            translation_result = self._call_openai_with_retry(prompt)
            translated_title, translated_content = self._parse_translation_result(
                translation_result
            )

            # Create new chapter in target language with transaction safety
            translated_chapter = self._create_translated_chapter(
                source_chapter, target_language, translated_title, translated_content
            )

            logger.info(
                f"Successfully translated chapter {source_chapter.id} to {target_language_code}"
            )
            return translated_chapter

        except Language.DoesNotExist:
            raise ValidationError(f"Target language '{target_language_code}' not found")
        except ValidationError:
            raise  # Re-raise validation errors as-is
        except Exception as e:
            logger.error(
                f"Translation failed for chapter {source_chapter.id}: {str(e)}"
            )
            raise APIError(f"Translation failed: {str(e)}")

    def _validate_chapter_content(self, chapter: Chapter) -> None:
        """Validate chapter content before translation"""
        if not chapter.content:
            raise ValidationError("Chapter content is empty")

        if len(chapter.content) < self.MIN_CONTENT_LENGTH:
            raise ValidationError(
                f"Content too short (minimum {self.MIN_CONTENT_LENGTH} characters)"
            )

        if len(chapter.content) > self.MAX_CONTENT_LENGTH:
            raise ValidationError(
                f"Content too long (maximum {self.MAX_CONTENT_LENGTH} characters)"
            )

        if not chapter.book.language:
            raise ValidationError("Source chapter must have a language set")

    def _get_target_language(self, language_code: str) -> Language:
        """Get and validate target language"""
        try:
            return Language.objects.get(code=language_code)
        except Language.DoesNotExist:
            raise ValidationError(f"Target language '{language_code}' not found")

    def _enforce_rate_limit(self) -> None:
        """Simple rate limiting to prevent API abuse"""
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time

        if time_since_last_request < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last_request
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def _call_openai_with_retry(self, prompt: str) -> str:
        """Call OpenAI API with retry logic"""
        last_exception = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )

                if not response.choices:
                    raise APIError("No response choices returned from OpenAI")

                translated_content = response.choices[0].message.content
                if not translated_content:
                    raise APIError("Empty response from OpenAI")

                return translated_content.strip()

            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()

                if "rate limit" in error_msg:
                    if attempt < self.MAX_RETRIES - 1:
                        sleep_time = self.RETRY_DELAY * (
                            2**attempt
                        )  # Exponential backoff
                        logger.warning(f"Rate limit hit, retrying in {sleep_time}s")
                        time.sleep(sleep_time)
                        continue
                    else:
                        raise RateLimitError("Rate limit exceeded, max retries reached")

                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(
                        f"API call failed (attempt {attempt + 1}), retrying: {e}"
                    )
                    time.sleep(self.RETRY_DELAY)
                    continue

        raise APIError(f"Failed after {self.MAX_RETRIES} attempts: {last_exception}")

    def _build_translation_prompt(
        self, title: str, content: str, source_lang: str, target_lang: str
    ):
        """Build translation prompt for both title and content"""
        return f"""
        Please translate the following chapter title and content from {source_lang} to {target_lang}.
        Maintain the original meaning, tone, and style. Keep proper formatting.

        Please format your response exactly as follows:
        TITLE: [translated title here]
        CONTENT: [translated content here]

        Chapter Title:
        {title}

        Chapter Content:
        {content}
        """

    def _parse_translation_result(self, translation_result: str) -> tuple[str, str]:
        """Parse the translation result to extract title and content"""
        try:
            lines = translation_result.strip().split("\n")
            title_line = None
            content_start = None

            # Find TITLE and CONTENT markers
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                if line_stripped.startswith("TITLE:"):
                    title_line = line_stripped[6:].strip()
                elif line_stripped.startswith("CONTENT:"):
                    content_start = i
                    break

            if title_line is None:
                logger.warning("Could not find TITLE marker in translation result")
                # Fallback: use first non-empty line as title
                for line in lines:
                    if line.strip():
                        title_line = line.strip()
                        break
                else:
                    title_line = "Untitled"

            if content_start is None:
                logger.warning("Could not find CONTENT marker in translation result")
                # Fallback: use everything after the first line as content
                content_lines = lines[1:] if len(lines) > 1 else []
            else:
                # Get everything after CONTENT: line
                content_lines = lines[content_start:]
                if content_lines and content_lines[0].strip().startswith("CONTENT:"):
                    # Remove the CONTENT: part from first line
                    first_line = content_lines[0].strip()[8:].strip()
                    if first_line:
                        content_lines[0] = first_line
                    else:
                        content_lines = content_lines[1:]

            translated_content = "\n".join(content_lines).strip()

            if not translated_content:
                raise APIError("Empty content in translation result")

            return title_line, translated_content

        except Exception as e:
            logger.error(f"Failed to parse translation result: {e}")
            # Fallback: treat entire result as content, generate simple title
            return "Translated Chapter", translation_result.strip()

    @transaction.atomic
    def _create_translated_chapter(
        self,
        source_chapter: Chapter,
        target_language: Language,
        translated_title: str,
        translated_content: str,
    ) -> Chapter:
        """Create a new chapter with translated content using transaction safety"""
        try:
            # Find or create target book
            target_book = source_chapter.book.bookmaster.books.filter(
                language=target_language
            ).first()

            if not target_book:
                # Create new book in target language
                target_book = source_chapter.book.bookmaster.books.create(
                    title=f"{source_chapter.book.title} ({target_language.name})",
                    language=target_language,
                    description=source_chapter.book.description,
                )
                logger.info(f"Created new book: {target_book.title}")

            # Check if translation already exists
            existing_chapter = target_book.chapters.filter(
                chaptermaster=source_chapter.chaptermaster
            ).first()

            if existing_chapter:
                logger.warning(
                    f"Chapter already exists in {target_language.name}, updating content"
                )
                existing_chapter.title = translated_title
                existing_chapter.content = translated_content
                existing_chapter.save()
                target_book.update_metadata()
                return existing_chapter

            # Create translated chapter
            translated_chapter = Chapter.objects.create(
                title=translated_title,
                chaptermaster=source_chapter.chaptermaster,
                book=target_book,
                content=translated_content,
            )
            translated_chapter.generate_excerpt()

            # Update book metadata
            target_book.update_metadata()

            logger.info(f"Created translated chapter: {translated_chapter.title}")
            return translated_chapter

        except Exception as e:
            logger.error(f"Failed to create translated chapter: {str(e)}")
            raise APIError(f"Database error creating translated chapter: {str(e)}")


def process_translation_jobs():
    """Process pending translation jobs with concurrency protection"""
    service = TranslationService()
    processed_count = 0
    max_jobs = 200

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

        except ValidationError as e:
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

        except (APIError, TranslationError) as e:
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
