"""
Base service class with provider abstraction.

All AI-powered services inherit from this base class.
"""

import logging
from typing import Optional

from ai_services.core import BaseAIProvider, ProviderRegistry
from ai_services.core.exceptions import ConfigurationError
from ai_services.config import AIServicesConfig

logger = logging.getLogger(__name__)


class BaseAIService:
    """
    Base service class with provider abstraction.

    Subclasses specify service-specific logic and delegate
    AI operations to the configured provider.
    """

    # Subclasses should override these
    DEFAULT_MODEL = "gpt-4o-mini"
    DEFAULT_MAX_TOKENS = 4000
    DEFAULT_TEMPERATURE = 0.3
    DEFAULT_PROVIDER = "openai"
    SERVICE_NAME = None  # e.g., "translation", "analysis"

    def __init__(
        self,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        api_key: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize service with provider.

        Args:
            provider_name: Provider to use ("openai", "gemini")
            model: Model name (provider-specific)
            max_tokens: Maximum tokens in response
            temperature: Randomness (0.0-1.0)
            api_key: API key for provider (optional, loads from settings)
            **kwargs: Additional provider-specific options

        Raises:
            ConfigurationError: If provider or API key not configured
        """
        # Determine provider
        if provider_name is None:
            # Try service-specific provider first
            if self.SERVICE_NAME:
                provider_name = AIServicesConfig.get_provider_for_service(
                    self.SERVICE_NAME
                )
            else:
                provider_name = AIServicesConfig.get_default_provider()

        self.provider_name = provider_name.lower()

        # Get provider class from registry
        provider_class = ProviderRegistry.get(self.provider_name)

        # Get configuration from settings
        if api_key is None:
            api_key = AIServicesConfig.get_api_key(self.provider_name)

        if not api_key:
            raise ConfigurationError(
                f"No API key configured for provider '{self.provider_name}'. "
                f"Please set {self.provider_name.upper()}_API_KEY in settings."
            )

        # Set configuration (use provided values or load from settings)
        if model is None:
            model = AIServicesConfig.get_model(self.provider_name, self.SERVICE_NAME)

        if max_tokens is None:
            max_tokens = AIServicesConfig.get_max_tokens(
                self.provider_name, self.SERVICE_NAME
            )

        if temperature is None:
            temperature = AIServicesConfig.get_temperature(
                self.provider_name, self.SERVICE_NAME
            )

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Initialize provider
        self.provider: BaseAIProvider = provider_class(
            api_key=api_key, model=self.model, **kwargs
        )

        logger.info(
            f"Initialized {self.__class__.__name__} with "
            f"provider={self.provider_name}, model={self.model}, "
            f"max_tokens={self.max_tokens}, temperature={self.temperature}"
        )

    def get_provider_info(self):
        """
        Get information about the current provider.

        Returns:
            Dictionary with provider information
        """
        return {
            "service": self.__class__.__name__,
            "provider": self.provider_name,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

    def __repr__(self):
        """String representation"""
        return (
            f"{self.__class__.__name__}("
            f"provider={self.provider_name}, model={self.model})"
        )
