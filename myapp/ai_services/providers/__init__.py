"""
AI provider implementations.

This module contains concrete implementations of the BaseAIProvider interface
for different AI services (OpenAI, Gemini, etc.).

Providers are automatically registered when this module is imported.
"""

from ai_services.core import ProviderRegistry
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider

# Auto-register providers
ProviderRegistry.register("openai", OpenAIProvider)
ProviderRegistry.register("gemini", GeminiProvider)

__all__ = [
    "OpenAIProvider",
    "GeminiProvider",
]
