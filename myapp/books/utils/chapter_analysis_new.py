"""
COMPATIBILITY WRAPPER: Chapter analysis service.

This file provides backward compatibility with the old ChapterAnalysisService
while using the new modular ai_services package under the hood.

DEPRECATED: This wrapper will be removed in a future version.
New code should use: from ai_services.services import AnalysisService
"""

import warnings
import logging

from ai_services.services import AnalysisService as NewAnalysisService
from ai_services.core.exceptions import (
    AIServiceError,
    APIError as NewAPIError,
)

logger = logging.getLogger(__name__)


# Backward-compatible exception classes
class AnalysisError(AIServiceError):
    """Base exception for chapter analysis errors (backward compatible)"""

    pass


class APIError(AnalysisError):
    """API related error (backward compatible)"""

    pass


class ChapterAnalysisService:
    """
    DEPRECATED: Backward-compatible wrapper for the new AnalysisService.

    This class maintains the old interface but delegates to the new
    provider-agnostic AnalysisService.

    Migration Guide:
        OLD:
            from books.utils import ChapterAnalysisService
            service = ChapterAnalysisService()
            result = service.extract_entities_and_summary(content, "zh")

        NEW:
            from ai_services.services import AnalysisService
            service = AnalysisService()  # Uses default provider from settings
            result = service.extract_entities_and_summary(content, "zh")

            # Or specify provider explicitly:
            service = AnalysisService(provider_name="gemini")
    """

    def __init__(self):
        """
        Initialize the chapter analysis service.

        DEPRECATED: Use ai_services.services.AnalysisService instead.
        """
        warnings.warn(
            "ChapterAnalysisService is deprecated. "
            "Use ai_services.services.AnalysisService instead. "
            "See migration guide in documentation.",
            DeprecationWarning,
            stacklevel=2,
        )

        try:
            # Initialize new service with OpenAI to maintain current behavior
            # (unless user has configured a different default provider)
            self._service = NewAnalysisService()
            logger.debug(
                f"ChapterAnalysisService initialized using new AnalysisService "
                f"with provider={self._service.provider_name}"
            )
        except Exception as e:
            # Convert new exceptions to old exception types for compatibility
            raise APIError(str(e))

    def extract_entities_and_summary(self, content, language_code="zh"):
        """
        Extract entities and summary from chapter content.

        Args:
            content (str): Chapter content to analyze
            language_code (str): Source language code (default: "zh")

        Returns:
            dict: Extracted entities and summary with keys:
                - characters: list of character names
                - places: list of place names
                - terms: list of special terms
                - summary: brief chapter summary

        Raises:
            APIError: On API communication errors
            AnalysisError: On other analysis errors
        """
        try:
            return self._service.extract_entities_and_summary(content, language_code)
        except NewAPIError as e:
            # Convert new exception to old exception type
            raise APIError(str(e))
        except AIServiceError as e:
            raise AnalysisError(str(e))
        except Exception as e:
            raise AnalysisError(f"Unexpected error: {e}")
