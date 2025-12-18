"""
COMPATIBILITY WRAPPER: Chapter translation service.

This file provides backward compatibility with the old ChapterTranslationService
while using the new modular ai_services package under the hood.

DEPRECATED: This wrapper will be removed in a future version.
New code should use: from ai_services.services import TranslationService
"""

import warnings
import logging

from ai_services.services import TranslationService as NewTranslationService
from ai_services.core.exceptions import (
    AIServiceError,
    APIError as NewAPIError,
    RateLimitError as NewRateLimitError,
    ValidationError as NewValidationError,
)

logger = logging.getLogger("translation")


# Backward-compatible exception classes
class TranslationError(AIServiceError):
    """Base exception for translation errors (backward compatible)"""

    pass


class TranslationValidationError(TranslationError):
    """Validation error for translation input (backward compatible)"""

    pass


class APIError(TranslationError):
    """API related error (backward compatible)"""

    pass


class RateLimitError(TranslationError):
    """Rate limit exceeded error (backward compatible)"""

    pass


class ChapterTranslationService:
    """
    DEPRECATED: Backward-compatible wrapper for the new TranslationService.

    This class maintains the old interface but delegates to the new
    provider-agnostic TranslationService.

    Migration Guide:
        OLD:
            from books.utils import ChapterTranslationService
            service = ChapterTranslationService()
            translated = service.translate_chapter(chapter, "en")

        NEW:
            from ai_services.services import TranslationService
            service = TranslationService()  # Uses default provider from settings
            translated = service.translate_chapter(chapter, "en")

            # Or specify provider explicitly:
            service = TranslationService(provider_name="gemini")
    """

    def __init__(self):
        """
        Initialize the chapter translation service.

        DEPRECATED: Use ai_services.services.TranslationService instead.
        """
        warnings.warn(
            "ChapterTranslationService is deprecated. "
            "Use ai_services.services.TranslationService instead. "
            "See migration guide in documentation.",
            DeprecationWarning,
            stacklevel=2,
        )

        try:
            # Initialize new service (uses provider from settings)
            self._service = NewTranslationService()
            logger.debug(
                f"ChapterTranslationService initialized using new TranslationService "
                f"with provider={self._service.provider_name}"
            )
        except Exception as e:
            # Convert new exceptions to old exception types for compatibility
            raise APIError(str(e))

    def translate_chapter(self, source_chapter, target_language_code: str):
        """
        Translate a chapter to target language.

        Args:
            source_chapter: Source Chapter model instance
            target_language_code: Target language code (e.g., "en", "zh")

        Returns:
            Translated Chapter model instance

        Raises:
            TranslationValidationError: If input validation fails
            APIError: If translation API call fails
            RateLimitError: If rate limit exceeded
            TranslationError: For other translation errors
        """
        try:
            return self._service.translate_chapter(source_chapter, target_language_code)

        except NewValidationError as e:
            # Convert new exception to old exception type
            raise TranslationValidationError(str(e))
        except NewRateLimitError as e:
            raise RateLimitError(str(e))
        except NewAPIError as e:
            raise APIError(str(e))
        except AIServiceError as e:
            raise TranslationError(str(e))
        except Exception as e:
            raise TranslationError(f"Unexpected error: {e}")
