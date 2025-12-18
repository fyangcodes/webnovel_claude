"""
Provider registry for managing AI providers.

Allows dynamic registration and retrieval of AI providers.
"""

from typing import Type, Dict, List

from .base import BaseAIProvider
from .exceptions import ProviderNotFoundError


class ProviderRegistry:
    """
    Central registry for AI providers.

    Providers are registered by name and can be retrieved dynamically.
    This allows the service layer to be completely provider-agnostic.
    """

    # Class-level storage for registered providers
    _providers: Dict[str, Type[BaseAIProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: Type[BaseAIProvider]) -> None:
        """
        Register a provider.

        Args:
            name: Provider name (e.g., "openai", "gemini")
            provider_class: Provider class (must inherit from BaseAIProvider)

        Raises:
            TypeError: If provider_class doesn't inherit from BaseAIProvider
        """
        if not issubclass(provider_class, BaseAIProvider):
            raise TypeError(
                f"{provider_class.__name__} must inherit from BaseAIProvider"
            )

        cls._providers[name.lower()] = provider_class

    @classmethod
    def get(cls, name: str) -> Type[BaseAIProvider]:
        """
        Get a provider class by name.

        Args:
            name: Provider name (case-insensitive)

        Returns:
            Provider class

        Raises:
            ProviderNotFoundError: If provider not found
        """
        name = name.lower()
        if name not in cls._providers:
            available = ", ".join(cls.list_providers())
            raise ProviderNotFoundError(
                f"Provider '{name}' not found. Available providers: {available}"
            )
        return cls._providers[name]

    @classmethod
    def list_providers(cls) -> List[str]:
        """
        List all registered providers.

        Returns:
            List of provider names
        """
        return sorted(cls._providers.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Check if a provider is registered.

        Args:
            name: Provider name (case-insensitive)

        Returns:
            True if registered, False otherwise
        """
        return name.lower() in cls._providers

    @classmethod
    def unregister(cls, name: str) -> None:
        """
        Unregister a provider.

        Useful for testing or dynamic provider management.

        Args:
            name: Provider name (case-insensitive)
        """
        name = name.lower()
        if name in cls._providers:
            del cls._providers[name]

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered providers.

        Useful for testing.
        """
        cls._providers.clear()
