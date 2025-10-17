"""
OpenAI translation service with improved error handling and validation
"""

import json
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

            # Create prompt for translation (title + content + context)
            prompt = self._build_translation_prompt(
                source_chapter,
                target_language,
            )

            # Call OpenAI API with retry logic
            translation_result = self._call_openai_with_retry(prompt)
            translated_title, translated_content, entity_mappings, translator_notes = (
                self._parse_translation_result(translation_result)
            )

            # Create new chapter in target language with transaction safety
            translated_chapter = self._create_translated_chapter(
                source_chapter,
                target_language,
                translated_title,
                translated_content,
                entity_mappings,
                translator_notes,
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

    def _get_previous_chapters_context(self, source_chapter, target_language, count=3):
        """Get context from previous chapters including titles and summaries"""
        from books.models import Chapter, ChapterContext

        # Get current chapter number
        current_chapter_num = source_chapter.chaptermaster.chapter_number

        # Get previous chapters in the same book
        previous_chapters = (
            Chapter.objects.filter(
                book=source_chapter.book,
                chaptermaster__chapter_number__lt=current_chapter_num,
            )
            .select_related("chaptermaster")
            .order_by("-chaptermaster__chapter_number")[:count]
        )

        context_info = []
        for chapter in reversed(previous_chapters):  # Show in chronological order
            chapter_num = chapter.chaptermaster.chapter_number
            original_title = chapter.title

            # Try to get translated title from the same chaptermaster in target language
            translated_title = None
            try:
                # Find the target book in the target language
                target_book = chapter.chaptermaster.bookmaster.books.filter(
                    language=target_language
                ).first()
                if target_book:
                    # Find the chapter in the target language for the same chaptermaster
                    translated_chapter = Chapter.objects.get(
                        chaptermaster=chapter.chaptermaster, book=target_book
                    )
                    translated_title = translated_chapter.title
            except Chapter.DoesNotExist:
                pass  # No translation available yet

            # Get summary if available
            try:
                context = ChapterContext.objects.get(chapter=chapter)
                summary = context.summary or "No summary available"
            except ChapterContext.DoesNotExist:
                summary = "No summary available"

            context_info.append(
                {
                    "number": chapter_num,
                    "original_title": original_title,
                    "translated_title": translated_title,
                    "summary": summary,
                }
            )

        return context_info

    def _build_translation_prompt(self, source_chapter, target_language):
        """Build enhanced translation prompt with entity consistency"""
        from books.models import ChapterContext

        source_lang = source_chapter.book.language.name
        target_lang = target_language.name
        target_code = target_language.code

        # Get chapter context for entities (current chapter)
        try:
            context = ChapterContext.objects.get(chapter=source_chapter)
            chapter_entities = context.key_terms
        except ChapterContext.DoesNotExist:
            chapter_entities = {}

        # Get relevant entity translations for this chapter only
        relevant_entities = self._get_relevant_entities(
            source_chapter.book.bookmaster, chapter_entities, target_code
        )

        # Get previous chapters context
        previous_chapters = self._get_previous_chapters_context(
            source_chapter, target_language
        )

        # Build the enhanced prompt with hierarchical structure
        prompt_parts = [
            f"# TRANSLATION TASK",
            f"Translate this chapter from **{source_lang}** to **{target_lang}**.",
            f"Preserve paragraph breaks and dialogue formatting.",
            f"Maintain the original meaning, tone, and style{""}.",
            "",
        ]

        # Translation Rules Section
        prompt_parts.append("## TRANSLATION RULES")

        # Consistency subsection
        prompt_parts.extend(
            [
                "### CONSISTENCY",
                "- Use translations from the FOUND ENTITIES section if available.",
                "- Translate entities in NEW ENTITIES section consistently with the established style.",
                "- Reference the CONTEXT section to maintain consistency with previous translations and ensure story continuity.",
                "- For proper nouns (e.g., names, places), use Pinyin transliteration for characters (e.g., 陆飞 as Lu Fei) and standard English names for places (e.g., 广州 as Guangzhou) unless specified otherwise.",
                "",
            ]
        )

        # Cultural considerations
        prompt_parts.extend(
            [
                "### CULTURAL CONSIDERATIONS",
                f"- For idiomatic expressions or culturally specific terms, provide a natural {target_lang} equivalent that conveys the same meaning.",
                "- If a term is untranslatable, use transliteration or a descriptive phrase and explain in the ENTITY_MAPPINGS section.",
                "",
            ]
        )

        # Formating guidlines
        prompt_parts.extend(
            [
                "### FORMATTING GUIDELINES",
                "- Preserve paragraph breaks and use quotation marks for dialogue.",
                "- Format the translated text as plain text with clear paragraph separation.",
                "- Do not add markup (e.g., HTML, Markdown) unless specified.",
                "",
            ]
        )

        # Error Handling
        prompt_parts.extend(
            [
                "### ERROR HANDLING",
                '- If a term is ambiguous, select the most contextually appropriate translation and note the choice in the ENTITY_MAPPINGS section (e.g., {"老板": "Boss (assumed to be employer)"}).',
                "- For untranslatable terms, provide a transliteration or description and explain in the ENTITY_MAPPINGS.",
                "- Use TRANSLATOR_NOTES to document assumptions, clarifications, cultural context, or translation challenges encountered.",
                "- Include any important decisions made during translation that future translators should be aware of.",
                "",
            ]
        )

        # Response Format subsection
        prompt_parts.extend(
            [
                "### RESPONSE FORMAT",
                "Please format your response exactly as follows:",
                "",
                "TITLE: [translated title here]",
                "CONTENT: [translated content here]",
                "ENTITY_MAPPINGS: [JSON object with source→translation pairs for entities that appear in your translation]",
                "TRANSLATOR_NOTES: [Any assumptions, clarifications, or issues encountered]",
                "",
                'Format: {"原文名": "Translated Name", "另一个名": "Another Name"}',
                "",
            ]
        )

        # Entities Section
        prompt_parts.append("## ENTITIES")

        # Found Entities subsection - show existing translations
        if relevant_entities:
            prompt_parts.extend(
                [
                    "### FOUND ENTITIES",
                    "Previously translated entities to use:",
                    "",
                    relevant_entities,
                    "",
                ]
            )

        # New Entities subsection - only show entities that don't have translations yet
        prompt_parts.append("### NEW ENTITIES")
        if chapter_entities:
            new_entities_by_category = self._get_new_entities_only(
                source_chapter.book.bookmaster, chapter_entities, target_code
            )

            if new_entities_by_category:
                entities_display = []
                for category, entities in new_entities_by_category.items():
                    if entities:
                        entities_display.append(
                            f"**{category.title()}:** {', '.join(entities)}"
                        )

                if entities_display:
                    prompt_parts.extend(
                        [
                            "Key entities in current chapter that need translation:",
                            "\n".join(entities_display),
                            "",
                        ]
                    )
                else:
                    prompt_parts.extend(
                        [
                            "All entities in current chapter already have established translations.",
                            "",
                        ]
                    )
            else:
                prompt_parts.extend(
                    [
                        "All entities in current chapter already have established translations.",
                        "",
                    ]
                )
        else:
            prompt_parts.extend(
                [
                    "No entities identified in current chapter.",
                    "",
                ]
            )

        # Context Section
        prompt_parts.extend(
            [
                "## CONTEXT",
                "**Title and summary of previous chapters**",
            ]
        )

        # Previous chapters subsection
        if previous_chapters:
            for chapter_info in previous_chapters:
                # Format title with translation if available
                if chapter_info["translated_title"]:
                    title_line = f"**{chapter_info['original_title']}** → **{chapter_info['translated_title']}** (Chapter {chapter_info['number']})"
                else:
                    title_line = f"**{chapter_info['original_title']}** (Chapter {chapter_info['number']})"

                prompt_parts.extend(
                    [
                        title_line,
                        f"{chapter_info['summary']}",
                        "",
                    ]
                )
        else:
            prompt_parts.extend(
                [
                    "No previous chapters available.",
                    "",
                ]
            )

        # Source Text Section
        prompt_parts.extend(
            [
                "## SOURCE TEXT",
                f"**Title:** {source_chapter.title}",
                "",
                f"**Content:**",
                source_chapter.content,
            ]
        )

        return "\n".join(prompt_parts)

    def _get_new_entities_only(
        self, bookmaster, chapter_entities, target_language_code
    ):
        """Get only entities that don't have translations yet"""
        from books.models import BookEntity

        if not chapter_entities:
            return {}

        # Get existing entity translations for this book and target language
        existing_entities = set()
        book_entities = BookEntity.objects.filter(bookmaster=bookmaster)

        for entity in book_entities:
            if entity.translations and target_language_code in entity.translations:
                existing_entities.add(entity.source_name)

        # Filter out entities that already have translations
        new_entities = {}
        for category in ["characters", "places", "terms"]:
            category_entities = chapter_entities.get(category, [])
            new_category_entities = []

            for entity in category_entities:
                if entity not in existing_entities:
                    new_category_entities.append(entity)

            if new_category_entities:
                new_entities[category] = new_category_entities

        return new_entities

    def _get_relevant_entities(
        self, bookmaster, chapter_entities, target_language_code
    ):
        """Get entity translations only for entities present in current chapter"""
        from books.models import BookEntity

        if not chapter_entities:
            return ""

        guidelines = []

        # Collect all entities mentioned in this chapter
        current_chapter_entities = []
        for category in ["characters", "places", "terms"]:
            current_chapter_entities.extend(chapter_entities.get(category, []))

        if not current_chapter_entities:
            return ""

        # Find existing translations only for entities in this chapter
        for entity_name in current_chapter_entities:
            try:
                entity = BookEntity.objects.get(
                    bookmaster=bookmaster, source_name=entity_name
                )

                translation = entity.get_translation(target_language_code)
                if translation and translation != entity.source_name:
                    # Entity has a specific translation
                    guidelines.append(
                        f"- {entity.source_name} → {translation} ({entity.entity_type})"
                    )
                elif entity.translations:
                    # Entity exists but no translation for this language yet
                    guidelines.append(
                        f"- {entity.source_name} (translate as {entity.entity_type})"
                    )

            except BookEntity.DoesNotExist:
                # Entity not in database yet, will be handled as new entity
                continue

        return "\n".join(guidelines) if guidelines else ""

    def _parse_translation_result(
        self, translation_result: str
    ) -> tuple[str, str, dict, str]:
        """Parse the translation result to extract title, content, entity mappings, and translator notes"""
        try:
            lines = translation_result.strip().split("\n")
            title_line = None
            content_start = None
            content_end = None
            mappings_start = None
            notes_start = None
            entity_mappings = {}
            translator_notes = ""

            # Find TITLE, CONTENT, ENTITY_MAPPINGS, and TRANSLATOR_NOTES markers
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                if line_stripped.startswith("TITLE:"):
                    title_line = line_stripped[6:].strip()
                elif line_stripped.startswith("CONTENT:"):
                    content_start = i
                elif line_stripped.startswith("ENTITY_MAPPINGS:"):
                    content_end = i
                    mappings_start = i
                elif line_stripped.startswith("TRANSLATOR_NOTES:"):
                    notes_start = i
                    break

            # Parse title
            if title_line is None:
                logger.warning("Could not find TITLE marker in translation result")
                # Fallback: use first non-empty line as title
                for line in lines:
                    if line.strip():
                        title_line = line.strip()
                        break
                else:
                    title_line = "Untitled"

            # Parse content
            if content_start is None:
                logger.warning("Could not find CONTENT marker in translation result")
                # Fallback: use everything after the first line as content
                # Stop at ENTITY_MAPPINGS or TRANSLATOR_NOTES
                end_index = (
                    content_end
                    if content_end
                    else (notes_start if notes_start else len(lines))
                )
                content_lines = lines[1:end_index]
            else:
                # Get content between CONTENT: and ENTITY_MAPPINGS/TRANSLATOR_NOTES (or end)
                end_index = (
                    content_end
                    if content_end
                    else (notes_start if notes_start else len(lines))
                )
                content_lines = lines[content_start:end_index]

                if content_lines and content_lines[0].strip().startswith("CONTENT:"):
                    # Remove the CONTENT: part from first line
                    first_line = content_lines[0].strip()[8:].strip()
                    if first_line:
                        content_lines[0] = first_line
                    else:
                        content_lines = content_lines[1:]

            translated_content = "\n".join(content_lines).strip()

            # Parse entity mappings
            if mappings_start is not None:
                try:
                    mappings_line = lines[mappings_start].strip()
                    if mappings_line.startswith("ENTITY_MAPPINGS:"):
                        mappings_json = mappings_line[16:].strip()
                        if (
                            mappings_json
                            and mappings_json
                            != "[entity mappings in JSON format if requested above]"
                        ):
                            import json

                            entity_mappings = json.loads(mappings_json)
                            logger.debug(f"Parsed entity mappings: {entity_mappings}")
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse entity mappings: {e}")
                    entity_mappings = {}

            # Parse translator notes
            if notes_start is not None:
                try:
                    notes_line = lines[notes_start].strip()
                    if notes_line.startswith("TRANSLATOR_NOTES:"):
                        translator_notes = notes_line[17:].strip()
                        # Also check if notes continue on next lines
                        if notes_start + 1 < len(lines):
                            remaining_notes = []
                            for line in lines[notes_start + 1 :]:
                                line_stripped = line.strip()
                                # Stop at next section marker or empty lines at end
                                if line_stripped.startswith(
                                    (
                                        "TITLE:",
                                        "CONTENT:",
                                        "ENTITY_MAPPINGS:",
                                        "TRANSLATOR_NOTES:",
                                    )
                                ):
                                    break
                                remaining_notes.append(line)
                            if remaining_notes:
                                if translator_notes:
                                    translator_notes += (
                                        " " + "\n".join(remaining_notes).strip()
                                    )
                                else:
                                    translator_notes = "\n".join(
                                        remaining_notes
                                    ).strip()
                except Exception as e:
                    logger.warning(f"Failed to parse translator notes: {e}")
                    translator_notes = ""

            if not translated_content:
                raise APIError("Empty content in translation result")

            return title_line, translated_content, entity_mappings, translator_notes

        except Exception as e:
            logger.error(f"Failed to parse translation result: {e}")
            # Fallback: treat entire result as content, generate simple title
            return "Translated Chapter", translation_result.strip(), {}, ""

    @transaction.atomic
    def _create_translated_chapter(
        self,
        source_chapter: Chapter,
        target_language: Language,
        translated_title: str,
        translated_content: str,
        entity_mappings: dict = None,
        translator_notes: str = "",
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
                existing_chapter.translator_notes = translator_notes
                existing_chapter.save()
                target_book.update_metadata()
                return existing_chapter

            # Create translated chapter
            translated_chapter = Chapter.objects.create(
                title=translated_title,
                chaptermaster=source_chapter.chaptermaster,
                book=target_book,
                content=translated_content,
                translator_notes=translator_notes,
            )

            # Update book metadata
            target_book.update_metadata()

            # Store entity translations from AI response
            if entity_mappings:
                self._store_entity_mappings(
                    source_chapter.book.bookmaster,
                    entity_mappings,
                    target_language.code,
                )

            logger.info(f"Created translated chapter: {translated_chapter.title}")
            return translated_chapter

        except Exception as e:
            logger.error(f"Failed to create translated chapter: {str(e)}")
            raise APIError(f"Database error creating translated chapter: {str(e)}")

    def _store_entity_mappings(self, bookmaster, entity_mappings, target_language_code):
        """Store entity translations from AI response"""
        from books.models import BookEntity

        try:
            for source_name, translated_name in entity_mappings.items():
                if source_name and translated_name and source_name != translated_name:
                    try:
                        entity = BookEntity.objects.get(
                            bookmaster=bookmaster, source_name=source_name
                        )
                        # Store the translation
                        entity.set_translation(target_language_code, translated_name)
                        logger.debug(
                            f"Stored mapping: {source_name} → {translated_name}"
                        )

                    except BookEntity.DoesNotExist:
                        # Entity not in database yet, skip for now
                        logger.debug(
                            f"Entity {source_name} not found in database, skipping mapping"
                        )

            logger.info(f"Stored {len(entity_mappings)} entity mappings")

        except Exception as e:
            # Don't fail the translation if entity mapping fails
            logger.warning(f"Failed to store entity mappings: {e}")


def process_translation_jobs(max_jobs):
    """Process pending translation jobs with concurrency protection"""
    service = TranslationService()
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


class EntityExtractionService:
    """AI-based entity extraction service for chapter analysis"""

    def __init__(self):
        """Initialize the entity extraction service"""
        if not settings.OPENAI_API_KEY:
            raise APIError("OpenAI API key is not configured")

        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.max_content_length = 5000  # Limit for extraction to control costs

    def extract_entities_and_summary(self, content, language_code="zh"):
        """
        Extract entities and summary from chapter content using AI

        Args:
            content (str): Chapter content to analyze
            language_code (str): Source language code (default: zh for Chinese)

        Returns:
            dict: Extracted entities and summary
        """
        try:
            # Truncate content if too long (cost control)
            truncated_content = content[: self.max_content_length]
            if len(content) > self.max_content_length:
                logger.info(
                    f"Content truncated from {len(content)} to {self.max_content_length} chars for extraction"
                )

            prompt = self._build_extraction_prompt(truncated_content, language_code)

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temperature for consistent JSON output
                response_format={"type": "json_object"},  # Force JSON response
            )

            response_text = response.choices[0].message.content.strip()
            logger.debug(f"Raw extraction response: {response_text}")

            # Parse JSON response
            try:
                # Clean the response text
                cleaned_response = self._clean_json_response(response_text)
                result = json.loads(cleaned_response)
                self._validate_extraction_result(result)
                logger.info(
                    f"Successfully extracted entities: {len(result.get('characters', []))} chars, {len(result.get('places', []))} places, {len(result.get('terms', []))} terms"
                )
                return result

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse extraction JSON: {e}")
                logger.error(f"Raw response: {response_text}")
                return self._get_fallback_result(content)

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return self._get_fallback_result(content)

    def _build_extraction_prompt(self, content, language_code):
        """Build the AI prompt for entity extraction"""
        from books.models import Language

        try:
            language = Language.objects.get(code=language_code)
            language_name = language.name
        except Language.DoesNotExist:
            language_name = language_code

        prompt_parts = []
        prompt_parts.extend(
            [
                f"You are a text analysis expert. Analyze the provided {language_name} text and extract key entities for translation consistency. You must respond with valid JSON only—no additional text, explanations, prefixes, or logs. Start your response with '{' and end with '}'.",
                "",
                "Your task:",
                "1. Extract CHARACTER names: Only unique proper names of people or beings. Do not include professions, descriptors or generic terms.",
                "2. Extract PLACE names: Only specific named locations, buildings, or realms. Do not include generic places.",
                "3. Extract TERM names: Only special concepts, techniques, items, or titles that need consistent translation. Exclude common words.",
                f"4. Create a brief summary: 2-3 sentences max, in {language_name}, covering the chapter's content and key events.",
                "",
                "Rules:",
                "- Only extract proper nouns and named entities that appear in the text.",
                "- Exclude common words, generic terms, and descriptors.",
                "- Focus on entities central to the plot that need consistent translation.",
                "- Limit each category to the top 10 most important entities (or fewer if not applicable).",
                "- Prioritize entities mentioned multiple times.",
                "",
                "You must respond with valid JSON only. No additional text or explanations.",
                "",
                "Required JSON format:",
                "{",
                '"characters": ["name1", "name2"],',
                '"places": ["place1", "place2"],',
                '"terms": ["term1", "term2"],',
                f'"summary": "Brief summary in {language_name}"',
                "}",
                "",
                "Text to analyze:",
                f"{content}",
            ]
        )

        return "\n".join(prompt_parts)

    def _clean_json_response(self, response_text):
        """Clean and prepare JSON response for parsing"""
        # Remove any markdown code blocks
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        # Strip whitespace
        response_text = response_text.strip()

        # Try to find JSON object bounds if there's extra text
        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}")

        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            response_text = response_text[start_idx : end_idx + 1]

        return response_text

    def _validate_extraction_result(self, result):
        """Validate the extraction result structure"""
        required_keys = ["characters", "places", "terms", "summary"]

        for key in required_keys:
            if key not in result:
                raise ValidationError(f"Missing required key: {key}")

        # Ensure lists are actually lists
        for key in ["characters", "places", "terms"]:
            if not isinstance(result[key], list):
                raise ValidationError(f"{key} must be a list")

        # Ensure summary is string
        if not isinstance(result["summary"], str):
            raise ValidationError("summary must be a string")

    def _get_fallback_result(self, content):
        """Return fallback result when AI extraction fails"""
        return {
            "characters": [],
            "places": [],
            "terms": [],
            "summary": content[:200] + "..." if len(content) > 200 else content,
        }
