"""
AI Services Package

A modular, provider-agnostic package for AI-powered services.

Supports multiple AI providers (OpenAI, Gemini) with a unified interface.
Services can switch providers via configuration without code changes.

Quick Start:
    from ai_services.services import TranslationService, AnalysisService
    
    # Uses default provider from settings
    translation = TranslationService()
    result = translation.translate_chapter(chapter, "en")
    
    # Or specify provider explicitly
    analysis = AnalysisService(provider_name="gemini")
    entities = analysis.extract_entities_and_summary(content)

Configuration:
    See settings.py for AI_DEFAULT_PROVIDER and provider-specific settings.
"""

# Import providers to trigger auto-registration
from . import providers

# Export commonly used classes
from .core import (
    BaseAIProvider,
    ChatMessage,
    ChatCompletionResponse,
    ProviderRegistry,
    AIServiceError,
    APIError,
    RateLimitError,
    ValidationError,
    ConfigurationError,
)
from .config import AIServicesConfig

__version__ = "1.0.0"

__all__ = [
    # Core classes
    "BaseAIProvider",
    "ChatMessage",
    "ChatCompletionResponse",
    "ProviderRegistry",
    # Exceptions
    "AIServiceError",
    "APIError",
    "RateLimitError",
    "ValidationError",
    "ConfigurationError",
    # Configuration
    "AIServicesConfig",
]
