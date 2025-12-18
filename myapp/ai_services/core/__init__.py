"""
Core AI services abstractions.

This module provides the foundational classes for the AI services layer:
- BaseAIProvider: Abstract interface all providers must implement
- ChatMessage, ChatCompletionResponse: Unified data models
- Exception hierarchy: Unified error handling
- ProviderRegistry: Dynamic provider management
"""

from .base import BaseAIProvider
from .models import ChatMessage, ChatCompletionResponse
from .exceptions import (
    AIServiceError,
    ProviderError,
    APIError,
    RateLimitError,
    ValidationError,
    ConfigurationError,
    ProviderNotFoundError,
    ResponseParsingError,
)
from .registry import ProviderRegistry

__all__ = [
    # Base classes
    "BaseAIProvider",
    # Data models
    "ChatMessage",
    "ChatCompletionResponse",
    # Exceptions
    "AIServiceError",
    "ProviderError",
    "APIError",
    "RateLimitError",
    "ValidationError",
    "ConfigurationError",
    "ProviderNotFoundError",
    "ResponseParsingError",
    # Registry
    "ProviderRegistry",
]
