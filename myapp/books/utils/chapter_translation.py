"""
AI-powered chapter translation service with entity consistency.
"""

import json
import logging
import time
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from .base_ai_service import BaseAIService
from books.models import Chapter, Language, TranslationJob
from books.choices import ProcessingStatus

logger = logging.getLogger("translation")


class TranslationError(Exception):
    """Base exception for translation errors"""
    pass


class TranslationValidationError(TranslationError):
    """Validation error for translation input"""
    pass


class APIError(TranslationError):
    """OpenAI API related error"""
    pass


class RateLimitError(TranslationError):
    """Rate limit exceeded error"""
    pass


class ChapterTranslationService(BaseAIService):
    """AI-powered translation service with validation and error handling"""

    # Settings configuration
    MODEL_SETTING_NAME = 'TRANSLATION_MODEL'
    MAX_TOKENS_SETTING_NAME = 'TRANSLATION_MAX_TOKENS'
    TEMPERATURE_SETTING_NAME = 'TRANSLATION_TEMPERATURE'

    # Content validation limits
    MAX_CONTENT_LENGTH = 8000  # Conservative limit for token estimation
    MIN_CONTENT_LENGTH = 10
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds

    def __init__(self):
        """Initialize the translation service"""
        try:
            super().__init__()
        except ValueError as e:
            raise TranslationValidationError(str(e))

        # Validate additional required settings
        self._validate_settings(
            required_settings=[
                "OPENAI_API_KEY",
                "TRANSLATION_MODEL",
                "TRANSLATION_MAX_TOKENS",
                "TRANSLATION_TEMPERATURE",
            ]
        )

        self._last_request_time = 0
        self._min_request_interval = 1  # Minimum 1 second between requests

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

            # Log the raw response for debugging (first 500 chars)
            logger.debug(f"Raw AI response preview: {translation_result[:500]}...")

            translated_title, translated_content, entity_mappings, translator_notes = (
                self._parse_translation_result(translation_result)
            )

            # Log entity mappings for debugging
            if entity_mappings:
                logger.info(f"Received {len(entity_mappings)} entity mappings from AI: {list(entity_mappings.keys())}")
            else:
                logger.warning("No entity mappings received from AI translation")

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
            raise TranslationValidationError(f"Target language '{target_language_code}' not found")
        except TranslationValidationError:
            raise  # Re-raise validation errors as-is
        except Exception as e:
            logger.error(
                f"Translation failed for chapter {source_chapter.id}: {str(e)}"
            )
            raise APIError(f"Translation failed: {str(e)}")

    def _validate_chapter_content(self, chapter: Chapter) -> None:
        """Validate chapter content before translation"""
        if not chapter.content:
            raise TranslationValidationError("Chapter content is empty")

        if len(chapter.content) < self.MIN_CONTENT_LENGTH:
            raise TranslationValidationError(
                f"Content too short (minimum {self.MIN_CONTENT_LENGTH} characters)"
            )

        if len(chapter.content) > self.MAX_CONTENT_LENGTH:
            raise TranslationValidationError(
                f"Content too long (maximum {self.MAX_CONTENT_LENGTH} characters)"
            )

        if not chapter.book.language:
            raise TranslationValidationError("Source chapter must have a language set")

    def _get_target_language(self, language_code: str) -> Language:
        """Get and validate target language"""
        try:
            return Language.objects.get(code=language_code)
        except Language.DoesNotExist:
            raise TranslationValidationError(f"Target language '{language_code}' not found")

    def _enforce_rate_limit(self) -> None:
        """Simple rate limiting to prevent API abuse"""
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time

        if time_since_last_request < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last_request
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def _call_openai_with_retry(self, prompt: str) -> str:
        """Call OpenAI API with retry logic and JSON mode"""
        last_exception = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    response_format={"type": "json_object"},  # Force JSON response
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
            f"Maintain the original meaning, tone, and style.",
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
                "- For Chinese proper nouns (names, places), use simple Pinyin WITHOUT tone marks/diacritics (e.g., 陆飞 → Lu Fei, NOT Lù Fēi; 鲲邪 → Kun Xie, NOT Kūn Xié).",
                "- For place names, use standard English names when available (e.g., 广州 → Guangzhou, 北京 → Beijing).",
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
                "**CRITICAL: You MUST respond with valid JSON only. No additional text, explanations, or markdown formatting.**",
                "",
                "Required JSON structure:",
                "{",
                '  "title": "Translated chapter title",',
                '  "content": "Full translated chapter content with preserved paragraph breaks",',
                '  "entity_mappings": {',
                '    "source_entity1": "translated_entity1",',
                '    "source_entity2": "translated_entity2"',
                "  },",
                '  "translator_notes": "Any assumptions, clarifications, or issues encountered"',
                "}",
                "",
                "Important:",
                "- Start your response with '{' and end with '}'",
                "- entity_mappings must be a JSON object (use {} if no mappings)",
                "- For Chinese names in entity_mappings, use simple Pinyin WITHOUT tone marks (e.g., \"鲲邪\": \"Kun Xie\", NOT \"Kūn Xié\")",
                "- translator_notes should be a string (use empty string \"\" if no notes)",
                "- Preserve paragraph breaks in content using \\n\\n",
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
        """Parse the JSON translation result to extract title, content, entity mappings, and translator notes"""
        try:
            # Parse JSON response
            result = json.loads(translation_result)

            # Validate required keys
            required_keys = ["title", "content"]
            missing_keys = [key for key in required_keys if key not in result]
            if missing_keys:
                raise APIError(f"Missing required keys in JSON response: {', '.join(missing_keys)}")

            # Extract values
            title = result["title"]
            content = result["content"]
            entity_mappings = result.get("entity_mappings", {})
            translator_notes = result.get("translator_notes", "")

            # Validate types
            if not isinstance(title, str):
                raise APIError(f"Title must be a string, got {type(title).__name__}")
            if not isinstance(content, str):
                raise APIError(f"Content must be a string, got {type(content).__name__}")
            if not isinstance(entity_mappings, dict):
                logger.warning(f"Entity mappings must be a dict, got {type(entity_mappings).__name__}. Using empty dict.")
                entity_mappings = {}
            if not isinstance(translator_notes, str):
                logger.warning(f"Translator notes must be a string, got {type(translator_notes).__name__}. Converting to string.")
                translator_notes = str(translator_notes)

            # Validate non-empty content
            if not content.strip():
                raise APIError("Empty content in translation result")

            # Log successful parsing
            logger.info(
                f"Successfully parsed JSON translation: title='{title}', "
                f"content_length={len(content)}, entity_mappings_count={len(entity_mappings)}"
            )
            logger.debug(f"Entity mappings: {entity_mappings}")

            return title, content, entity_mappings, translator_notes

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse translation JSON: {e}")
            logger.error(f"Raw response: {translation_result[:500]}...")
            raise APIError(f"Invalid JSON response from AI: {e}")

        except Exception as e:
            logger.error(f"Failed to parse translation result: {e}")
            raise APIError(f"Failed to parse translation result: {e}")

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
            stored_count = 0
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
                        stored_count += 1

                    except BookEntity.DoesNotExist:
                        # Entity not in database yet, log a warning
                        # This can happen if:
                        # 1. Translation happened before entity extraction on original chapter
                        # 2. AI returned entities not in the original chapter's extraction
                        logger.warning(
                            f"Entity '{source_name}' not found in database. Translation '{translated_name}' cannot be stored. "
                            f"Ensure entity extraction has been run on the original language chapter first."
                        )

            logger.info(f"Stored {stored_count} out of {len(entity_mappings)} entity mappings")

        except Exception as e:
            # Don't fail the translation if entity mapping fails
            logger.warning(f"Failed to store entity mappings: {e}")
