"""
Books utilities package for text processing, analysis, and translation.

This package provides three main service classes:
- TextExtractor: Extract and parse text from uploaded files
- ChapterAnalysisService: AI-powered entity extraction and chapter summarization
- ChapterTranslationService: AI-powered chapter translation with entity consistency
"""

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
