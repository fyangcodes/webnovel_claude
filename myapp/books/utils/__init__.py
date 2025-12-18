"""
Books utilities package for text processing, analysis, and translation.

This package provides service classes for:
- BaseAIService: Base class for AI-powered services with shared configuration
- TextExtractor: Extract and parse text from uploaded files
- ChapterAnalysisService: AI-powered entity extraction and chapter summarization
- ChapterTranslationService: AI-powered chapter translation with entity consistency
- JobConcurrencyManager: Manage concurrent job processing limits
- update_book_keywords: Extract and populate search keywords from taxonomy and entities
- rebuild_bookmaster_entities: Rebuild entity data from ChapterContext records
"""

from .base_ai_service import BaseAIService
from .text_extraction import TextExtractor, decode_text
# Use new modular AI services with backward compatibility
from .chapter_analysis_new import ChapterAnalysisService, AnalysisError, APIError as AnalysisAPIError
from .chapter_translation_new import (
    ChapterTranslationService,
    TranslationError,
    TranslationValidationError,
    APIError as TranslationAPIError,
    RateLimitError,
)
from .job_concurrency import JobConcurrencyManager
from .keywords import update_book_keywords
from .entities import rebuild_bookmaster_entities, rebuild_single_chapter_entities

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
    # Keywords
    "update_book_keywords",
    # Entities
    "rebuild_bookmaster_entities",
    "rebuild_single_chapter_entities",
]
