"""
Provider-agnostic translation service with entity consistency.

This service handles chapter translation while maintaining entity consistency
across chapters and providing context-aware translations.
"""

import json
import logging
import time
from typing import Dict, Tuple, Optional, List

from ai_services.core import ChatMessage, ValidationError, RateLimitError, APIError
from ai_services.core.exceptions import ResponseParsingError
from ai_services.core.rate_limiter import get_rate_limiter, get_provider_limits
from .base_service import BaseAIService
from ai_services.prompts.translation import TranslationPromptBuilder

logger = logging.getLogger("translation")


class TranslationService(BaseAIService):
    """
    AI-powered translation service with entity consistency.

    This service is provider-agnostic and works with any registered provider.
    """

    SERVICE_NAME = "translation"
    DEFAULT_MAX_TOKENS = 16000
    DEFAULT_TEMPERATURE = 0.3

    # Content validation limits
    MAX_CONTENT_LENGTH = 8000  # Conservative limit for token estimation
    MIN_CONTENT_LENGTH = 10
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds

    def __init__(self, *args, **kwargs):
        """Initialize the translation service"""
        super().__init__(*args, **kwargs)
        self._last_request_time = 0
        self._min_request_interval = 1  # Minimum 1 second between requests

    def translate_chapter(
        self,
        source_chapter,  # Django Chapter model
        target_language_code: str,
    ):
        """
        Translate a chapter to target language.

        This method integrates with Django models while using
        provider-agnostic translation logic.

        Args:
            source_chapter: Django Chapter model instance
            target_language_code: Target language code (e.g., "en", "zh")

        Returns:
            Translated Chapter model instance

        Raises:
            ValidationError: If input validation fails
            APIError: If translation API call fails
            RateLimitError: If rate limit exceeded
        """
        from books.models import Language, Chapter
        from django.db import transaction

        # Validate input
        self._validate_chapter_content(source_chapter)

        # Get target language
        try:
            target_language = Language.objects.get(code=target_language_code)
        except Language.DoesNotExist:
            raise ValidationError(f"Target language '{target_language_code}' not found")

        # Rate limiting
        self._enforce_rate_limit()

        # Gather context from Django models
        context_data = self._gather_translation_context(source_chapter, target_language)

        # Translate (provider-agnostic)
        translation_result = self._translate_with_context(
            title=source_chapter.title,
            content=source_chapter.content,
            source_language=source_chapter.book.language.name,
            target_language=target_language.name,
            context=context_data,
        )

        # Create Django model with transaction safety
        translated_chapter = self._create_translated_chapter(
            source_chapter,
            target_language,
            translation_result,
        )

        logger.info(
            f"Successfully translated chapter {source_chapter.id} to "
            f"{target_language_code} using {self.provider_name}"
        )

        return translated_chapter

    def _translate_with_context(
        self,
        title: str,
        content: str,
        source_language: str,
        target_language: str,
        context: Dict,
    ) -> Dict:
        """
        Provider-agnostic translation with context.

        Args:
            title: Chapter title
            content: Chapter content
            source_language: Source language name
            target_language: Target language name
            context: Context data (entities, previous chapters)

        Returns:
            Dict with keys: title, content, entity_mappings, translator_notes, error_details (if error)
        """
        # Build prompt using template
        prompt_builder = TranslationPromptBuilder()
        prompt = prompt_builder.build(
            title=title,
            content=content,
            source_language=source_language,
            target_language=target_language,
            entities=context.get('entities', {}),
            previous_chapters=context.get('previous_chapters', []),
        )

        # Create message
        messages = [ChatMessage(role="user", content=prompt)]

        response_text = None
        try:
            # Call provider with retry
            response_text = self._call_with_retry(messages)

            # Parse and return result
            result = self._parse_translation_result(response_text)

            # Validate entity mappings if provided
            expected_entities = context.get('entities', {}).get('new_entities', [])
            if expected_entities:
                result = self._validate_entity_mappings(result, expected_entities, prompt, response_text, content)

            return result

        except (ResponseParsingError, ValidationError) as e:
            # Validation errors - record detailed information
            error_details = self._format_translation_error_details(
                error_type=type(e).__name__,
                error_message=str(e),
                prompt=prompt,
                response=response_text,
                title=title,
                content_preview=content[:500],
                context=context
            )
            logger.error(f"Translation validation failed: {e}\n{error_details}")

            # Re-raise with error details attached
            raise ValidationError(f"{str(e)}\n\nError Details:\n{error_details}")

        except Exception as e:
            # Other errors
            error_details = self._format_translation_error_details(
                error_type=type(e).__name__,
                error_message=str(e),
                prompt=prompt,
                response=response_text,
                title=title,
                content_preview=content[:500],
                context=context
            )
            logger.error(f"Translation failed: {e}\n{error_details}")

            # Re-raise with error details
            raise APIError(f"{str(e)}\n\nError Details:\n{error_details}")

    def _call_with_retry(self, messages: List[ChatMessage]) -> str:
        """
        Call provider with retry logic.

        Args:
            messages: List of ChatMessage objects

        Returns:
            Response content string

        Raises:
            APIError: If all retries fail
            RateLimitError: If rate limit persists after retries
        """
        last_exception = None

        # Get rate limiter and provider limits
        rate_limiter = get_rate_limiter()
        limits = get_provider_limits(self.provider_name)

        for attempt in range(self.MAX_RETRIES):
            try:
                logger.debug(f"Translation API call attempt {attempt + 1}/{self.MAX_RETRIES}")

                # Check rate limits before making API call
                rate_limiter.check_and_wait(
                    provider=self.provider_name,
                    requests_per_minute=limits.get('requests_per_minute'),
                    requests_per_day=limits.get('requests_per_day'),
                    max_wait_seconds=120  # Wait up to 2 minutes
                )

                response = self.provider.chat_completion(
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    response_format="json",
                )

                if not response.content:
                    raise APIError("Empty response from provider")

                logger.info(f"Translation successful: {response.total_tokens} tokens used")
                return response.content

            except RateLimitError as e:
                last_exception = e
                if attempt < self.MAX_RETRIES - 1:
                    sleep_time = self.RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Rate limit hit, retrying in {sleep_time}s")
                    time.sleep(sleep_time)
                    continue
                else:
                    logger.error("Rate limit exceeded, max retries reached")
                    raise

            except Exception as e:
                last_exception = e
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"API call failed (attempt {attempt + 1}), retrying: {e}")
                    time.sleep(self.RETRY_DELAY)
                    continue

        raise APIError(f"Failed after {self.MAX_RETRIES} attempts: {last_exception}")

    def _gather_translation_context(self, source_chapter, target_language) -> Dict:
        """
        Gather context data from Django models.

        Args:
            source_chapter: Source Chapter model
            target_language: Target Language model

        Returns:
            Dict with 'entities' and 'previous_chapters'
        """
        from books.models import ChapterContext

        target_code = target_language.code

        # Get chapter entities
        try:
            context = ChapterContext.objects.get(chapter=source_chapter)
            chapter_entities = context.key_terms
        except ChapterContext.DoesNotExist:
            chapter_entities = {}

        # Get entity translations
        entities = self._format_entities_for_prompt(
            source_chapter.book.bookmaster,
            chapter_entities,
            target_code,
        )

        # Get previous chapters context
        previous_chapters = self._get_previous_chapters_context(
            source_chapter,
            target_language,
        )

        return {
            'entities': entities,
            'previous_chapters': previous_chapters,
        }

    def _format_entities_for_prompt(
        self,
        bookmaster,
        chapter_entities: Dict,
        target_language_code: str,
    ) -> Dict[str, str]:
        """
        Format entities for prompt inclusion.

        Args:
            bookmaster: BookMaster model
            chapter_entities: Dict of entities from ChapterContext
            target_language_code: Target language code

        Returns:
            Dict with 'found' (existing translations) and 'new' (need translation)
        """
        from books.models import BookEntity

        if not chapter_entities:
            return {'found': '', 'new': ''}

        # Collect all entities mentioned in this chapter
        current_chapter_entities = []
        for category in ["characters", "places", "terms"]:
            current_chapter_entities.extend(chapter_entities.get(category, []))

        if not current_chapter_entities:
            return {'found': '', 'new': ''}

        # Find existing translations
        found_translations = []
        new_entities_by_category = {'characters': [], 'places': [], 'terms': []}

        for entity_name in current_chapter_entities:
            try:
                entity = BookEntity.objects.get(
                    bookmaster=bookmaster,
                    source_name=entity_name
                )

                translation = entity.get_translation(target_language_code)
                if translation and translation != entity.source_name:
                    # Has translation
                    found_translations.append(
                        f"- {entity.source_name} → {translation} ({entity.entity_type})"
                    )
                else:
                    # No translation yet
                    category = {
                        'character': 'characters',
                        'place': 'places',
                        'term': 'terms',
                    }.get(entity.entity_type, 'terms')

                    new_entities_by_category[category].append(entity_name)

            except BookEntity.DoesNotExist:
                # Entity not in database - categorize from chapter_entities
                for category in ["characters", "places", "terms"]:
                    if entity_name in chapter_entities.get(category, []):
                        new_entities_by_category[category].append(entity_name)
                        break

        # Format found translations
        found_str = "\n".join(found_translations) if found_translations else ""

        # Format new entities
        new_entities_parts = []
        for category, entities in new_entities_by_category.items():
            if entities:
                new_entities_parts.append(
                    f"**{category.title()}:** {', '.join(entities)}"
                )

        new_str = "\n".join(new_entities_parts) if new_entities_parts else ""

        return {'found': found_str, 'new': new_str}

    def _get_previous_chapters_context(
        self,
        source_chapter,
        target_language,
        count: int = 3,
    ) -> List[Dict]:
        """
        Get context from previous chapters.

        Args:
            source_chapter: Source Chapter model
            target_language: Target Language model
            count: Number of previous chapters to include

        Returns:
            List of dicts with chapter info
        """
        from books.models import Chapter, ChapterContext

        # Get current chapter number
        current_chapter_num = source_chapter.chaptermaster.chapter_number

        # Get previous chapters
        previous_chapters = (
            Chapter.objects.filter(
                book=source_chapter.book,
                chaptermaster__chapter_number__lt=current_chapter_num,
            )
            .select_related("chaptermaster")
            .order_by("-chaptermaster__chapter_number")[:count]
        )

        context_info = []
        for chapter in reversed(previous_chapters):  # Chronological order
            chapter_num = chapter.chaptermaster.chapter_number
            original_title = chapter.title

            # Try to get translated title
            translated_title = None
            try:
                target_book = chapter.chaptermaster.bookmaster.books.filter(
                    language=target_language
                ).first()
                if target_book:
                    translated_chapter = Chapter.objects.get(
                        chaptermaster=chapter.chaptermaster,
                        book=target_book
                    )
                    translated_title = translated_chapter.title
            except Chapter.DoesNotExist:
                pass

            # Get summary
            try:
                context = ChapterContext.objects.get(chapter=chapter)
                summary = context.summary or "No summary available"
            except ChapterContext.DoesNotExist:
                summary = "No summary available"

            context_info.append({
                "number": chapter_num,
                "original_title": original_title,
                "translated_title": translated_title,
                "summary": summary,
            })

        return context_info

    def _parse_translation_result(self, result_text: str) -> Dict:
        """
        Parse JSON translation result.

        Args:
            result_text: Raw JSON response

        Returns:
            Dict with title, content, entity_mappings, translator_notes

        Raises:
            ResponseParsingError: If JSON cannot be parsed
            ValidationError: If required fields missing
        """
        try:
            # Parse JSON
            result = json.loads(result_text)

            # Validate required keys
            required_keys = ["title", "content"]
            missing_keys = [key for key in required_keys if key not in result]
            if missing_keys:
                raise ValidationError(
                    f"Missing required keys in JSON response: {', '.join(missing_keys)}"
                )

            # Extract values
            title = result["title"]
            content = result["content"]
            entity_mappings = result.get("entity_mappings", {})
            translator_notes = result.get("translator_notes", "")

            # Validate types
            if not isinstance(title, str):
                raise ValidationError(f"Title must be a string, got {type(title).__name__}")
            if not isinstance(content, str):
                raise ValidationError(f"Content must be a string, got {type(content).__name__}")
            if not isinstance(entity_mappings, dict):
                logger.warning(f"Entity mappings should be dict, got {type(entity_mappings).__name__}. Using empty dict.")
                entity_mappings = {}
            if not isinstance(translator_notes, str):
                logger.warning(f"Translator notes should be string, got {type(translator_notes).__name__}. Converting.")
                translator_notes = str(translator_notes)

            # Validate non-empty content
            if not content.strip():
                raise ValidationError("Empty content in translation result")

            logger.info(
                f"Successfully parsed translation: title='{title}', "
                f"content_length={len(content)}, mappings_count={len(entity_mappings)}"
            )

            return {
                'title': title,
                'content': content,
                'entity_mappings': entity_mappings,
                'translator_notes': translator_notes,
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse translation JSON: {e}")
            logger.debug(f"Raw response: {result_text[:500]}...")
            raise ResponseParsingError(f"Invalid JSON response: {e}")
        except Exception as e:
            logger.error(f"Failed to parse translation result: {e}")
            raise

    def _create_translated_chapter(
        self,
        source_chapter,
        target_language,
        translation_result: Dict,
    ):
        """
        Create translated chapter in database.

        Args:
            source_chapter: Source Chapter model
            target_language: Target Language model
            translation_result: Dict with translation data

        Returns:
            Created/updated Chapter model
        """
        from books.models import Chapter
        from django.db import transaction

        with transaction.atomic():
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
                existing_chapter.title = translation_result['title']
                existing_chapter.content = translation_result['content']
                existing_chapter.translator_notes = translation_result.get('translator_notes', '')
                existing_chapter.save()
                target_book.update_metadata()

                # Store entity mappings
                entity_mappings = translation_result.get('entity_mappings', {})
                if entity_mappings:
                    self._store_entity_mappings(
                        source_chapter.book.bookmaster,
                        entity_mappings,
                        target_language.code,
                    )

                return existing_chapter

            # Create new translated chapter
            translated_chapter = Chapter.objects.create(
                title=translation_result['title'],
                chaptermaster=source_chapter.chaptermaster,
                book=target_book,
                content=translation_result['content'],
                translator_notes=translation_result.get('translator_notes', ''),
            )

            # Update book metadata
            target_book.update_metadata()

            # Store entity mappings
            entity_mappings = translation_result.get('entity_mappings', {})
            if entity_mappings:
                self._store_entity_mappings(
                    source_chapter.book.bookmaster,
                    entity_mappings,
                    target_language.code,
                )

            logger.info(f"Created translated chapter: {translated_chapter.title}")
            return translated_chapter

    def _validate_entity_mappings(
        self,
        result: Dict,
        expected_entities: List[str],
        prompt: str,
        response: str,
        content: str
    ) -> Dict:
        """
        Validate that expected entities have translations.

        Args:
            result: Translation result dict
            expected_entities: List of entity names that should be translated
            prompt: The prompt sent
            response: The response received
            content: Source content

        Returns:
            Result dict (unchanged if valid)

        Raises:
            ValidationError: If expected entities are missing translations
        """
        entity_mappings = result.get('entity_mappings', {})
        missing_entities = []

        for entity in expected_entities:
            if entity not in entity_mappings:
                missing_entities.append(entity)

        if missing_entities:
            error_msg = (
                f"Translation did not include mappings for {len(missing_entities)} expected entities: "
                f"{', '.join(missing_entities[:10])}"
            )
            if len(missing_entities) > 10:
                error_msg += f" (and {len(missing_entities) - 10} more)"

            # Include detailed error information
            error_details = self._format_translation_error_details(
                error_type="MissingEntityMappingsError",
                error_message=error_msg,
                prompt=prompt,
                response=response,
                title=result.get('title', ''),
                content_preview=content[:500],
                context={'expected_entities': expected_entities, 'received_mappings': list(entity_mappings.keys())}
            )

            logger.warning(f"{error_msg}\n{error_details}")

            # Add error details to result but don't raise - allow translation to proceed
            result['entity_validation_warning'] = error_msg
            result['missing_entities'] = missing_entities

        return result

    def _format_translation_error_details(
        self,
        error_type: str,
        error_message: str,
        prompt: str,
        response: Optional[str],
        title: str,
        content_preview: str,
        context: Dict
    ) -> str:
        """
        Format detailed error information for translation failures.

        Args:
            error_type: Type of error
            error_message: Error message
            prompt: The prompt sent
            response: The response received (may be None)
            title: Chapter title
            content_preview: Preview of content
            context: Translation context data

        Returns:
            Formatted error details string
        """
        details = []
        details.append(f"=== Translation Error Details ===")
        details.append(f"Error Type: {error_type}")
        details.append(f"Error Message: {error_message}")
        details.append(f"Provider: {self.provider_name}")
        details.append(f"Model: {getattr(self.provider, 'model', 'unknown')}")
        details.append(f"Title: {title}")
        details.append("")
        details.append(f"--- Content Preview (first 500 chars) ---")
        details.append(content_preview)
        details.append("")

        # Include context information
        if context:
            details.append(f"--- Translation Context ---")
            entities = context.get('entities', {})
            if entities:
                found_entities = entities.get('found_entities', [])
                new_entities = entities.get('new_entities', [])
                details.append(f"Found entities (with translations): {len(found_entities)}")
                if found_entities:
                    details.append(f"  {', '.join([e.get('source', '') for e in found_entities[:5]])}")
                details.append(f"New entities (need translation): {len(new_entities)}")
                if new_entities:
                    details.append(f"  {', '.join(new_entities[:10])}")
                    if len(new_entities) > 10:
                        details.append(f"  ... and {len(new_entities) - 10} more")

            previous_chapters = context.get('previous_chapters', [])
            if previous_chapters:
                details.append(f"Previous chapters for context: {len(previous_chapters)}")

            # Add expected vs received entities if available
            if 'expected_entities' in context:
                expected = context['expected_entities']
                received = context.get('received_mappings', [])
                details.append(f"Expected entities: {len(expected)}")
                details.append(f"Received mappings: {len(received)}")
                details.append(f"Missing: {len(expected) - len(set(expected) & set(received))}")

            details.append("")

        details.append(f"--- Prompt Sent ---")
        details.append(prompt[:3000] if len(prompt) > 3000 else prompt)
        if len(prompt) > 3000:
            details.append(f"... (prompt truncated, total length: {len(prompt)} chars)")
        details.append("")
        details.append(f"--- Response Received ---")
        if response:
            details.append(response[:3000] if len(response) > 3000 else response)
            if len(response) > 3000:
                details.append(f"... (response truncated, total length: {len(response)} chars)")
        else:
            details.append("(No response received)")
        details.append("")
        details.append(f"=== End Error Details ===")

        return "\n".join(details)

    def _store_entity_mappings(
        self,
        bookmaster,
        entity_mappings: Dict[str, str],
        target_language_code: str,
    ):
        """
        Store entity translations from AI response.

        Args:
            bookmaster: BookMaster model
            entity_mappings: Dict mapping source names to translations
            target_language_code: Target language code
        """
        from books.models import BookEntity

        try:
            stored_count = 0
            for source_name, translated_name in entity_mappings.items():
                if source_name and translated_name and source_name != translated_name:
                    try:
                        entity = BookEntity.objects.get(
                            bookmaster=bookmaster,
                            source_name=source_name
                        )
                        # Store the translation
                        entity.set_translation(target_language_code, translated_name)
                        logger.debug(f"Stored mapping: {source_name} → {translated_name}")
                        stored_count += 1

                    except BookEntity.DoesNotExist:
                        logger.warning(
                            f"Entity '{source_name}' not found in database. "
                            f"Translation '{translated_name}' cannot be stored. "
                            f"Ensure entity extraction has been run on the original chapter."
                        )

            logger.info(f"Stored {stored_count} out of {len(entity_mappings)} entity mappings")

        except Exception as e:
            # Don't fail translation if entity mapping storage fails
            logger.warning(f"Failed to store entity mappings: {e}")

    def _validate_chapter_content(self, chapter) -> None:
        """
        Validate chapter content before translation.

        Args:
            chapter: Chapter model

        Raises:
            ValidationError: If validation fails
        """
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

    def _enforce_rate_limit(self) -> None:
        """Simple rate limiting to prevent API abuse"""
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time

        if time_since_last_request < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last_request
            time.sleep(sleep_time)

        self._last_request_time = time.time()
