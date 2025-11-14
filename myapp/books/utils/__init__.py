"""
Books utilities package for text processing, analysis, and translation.

This package provides service classes for:
- BaseAIService: Base class for AI-powered services with shared configuration
- TextExtractor: Extract and parse text from uploaded files
- ChapterAnalysisService: AI-powered entity extraction and chapter summarization
- ChapterTranslationService: AI-powered chapter translation with entity consistency
- JobConcurrencyManager: Manage concurrent job processing limits
"""

from .base_ai_service import BaseAIService
from .text_extraction import TextExtractor, decode_text
from .chapter_analysis import ChapterAnalysisService, AnalysisError, APIError as AnalysisAPIError
from .chapter_translation import (
    ChapterTranslationService,
    TranslationError,
    TranslationValidationError,
    APIError as TranslationAPIError,
    RateLimitError,
)
from .job_concurrency import JobConcurrencyManager

__all__ = [
    # Base AI service
    "BaseAIService",
    # Text extraction
    "TextExtractor",
    "decode_text",
    # Chapter analysis
    "ChapterAnalysisService",
    "AnalysisError",
    "AnalysisAPIError",
    # Chapter translation
    "ChapterTranslationService",
    "TranslationError",
    "TranslationValidationError",
    "TranslationAPIError",
    "RateLimitError",
    # Job concurrency
    "JobConcurrencyManager",
]
