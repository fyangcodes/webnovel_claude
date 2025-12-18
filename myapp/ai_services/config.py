"""
Configuration management for AI services.

Provides centralized configuration loading and validation.
"""

from typing import Optional, Dict, Any
from django.conf import settings

from .core.exceptions import ConfigurationError


class AIServicesConfig:
    """
    Configuration manager for AI services.

    Loads configuration from Django settings and provides
    convenient access methods.
    """

    @staticmethod
    def get_default_provider() -> str:
        """
        Get the default AI provider.

        Returns:
            Provider name (e.g., "openai", "gemini")
        """
        return getattr(settings, "AI_DEFAULT_PROVIDER", "openai")

    @staticmethod
    def get_provider_for_service(service_name: str) -> str:
        """
        Get provider for a specific service.

        Args:
            service_name: Service name (e.g., "translation", "analysis")

        Returns:
            Provider name, falls back to default if not specified
        """
        setting_name = f"{service_name.upper()}_PROVIDER"
        default = AIServicesConfig.get_default_provider()
        return getattr(settings, setting_name, default)

    @staticmethod
    def get_api_key(provider_name: str) -> Optional[str]:
        """
        Get API key for a provider.

        Args:
            provider_name: Provider name (e.g., "openai", "gemini")

        Returns:
            API key or None if not configured

        Raises:
            ConfigurationError: If provider is unknown
        """
        key_mapping = {
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
        }

        setting_name = key_mapping.get(provider_name.lower())
        if not setting_name:
            raise ConfigurationError(f"Unknown provider: {provider_name}")

        return getattr(settings, setting_name, None)

    @staticmethod
    def get_model(provider_name: str, service_name: Optional[str] = None) -> str:
        """
        Get model name for a provider and service.

        Args:
            provider_name: Provider name (e.g., "openai", "gemini")
            service_name: Optional service name (e.g., "translation", "analysis")

        Returns:
            Model name

        Examples:
            get_model("openai", "translation") -> "gpt-4o-mini"
            get_model("gemini") -> "gemini-2.0-flash-exp"
        """
        provider = provider_name.upper()

        # Try service-specific model first
        if service_name:
            service = service_name.upper()
            setting_name = f"{provider}_{service}_MODEL"
            model = getattr(settings, setting_name, None)
            if model:
                return model

        # Fall back to provider default model
        setting_name = f"{provider}_DEFAULT_MODEL"
        model = getattr(settings, setting_name, None)
        if model:
            return model

        # Hard-coded defaults as last resort
        defaults = {
            "openai": "gpt-4o-mini",
            "gemini": "gemini-2.0-flash-exp",
        }
        return defaults.get(provider_name.lower(), "gpt-4o-mini")

    @staticmethod
    def get_max_tokens(
        provider_name: str, service_name: Optional[str] = None
    ) -> int:
        """
        Get max tokens for a provider and service.

        Args:
            provider_name: Provider name
            service_name: Optional service name

        Returns:
            Max tokens
        """
        provider = provider_name.upper()

        # Try service-specific setting first
        if service_name:
            service = service_name.upper()
            setting_name = f"{provider}_{service}_MAX_TOKENS"
            max_tokens = getattr(settings, setting_name, None)
            if max_tokens is not None:
                return int(max_tokens)

        # Default max tokens
        return 4000

    @staticmethod
    def get_temperature(
        provider_name: str, service_name: Optional[str] = None
    ) -> float:
        """
        Get temperature for a provider and service.

        Args:
            provider_name: Provider name
            service_name: Optional service name

        Returns:
            Temperature (0.0-1.0)
        """
        provider = provider_name.upper()

        # Try service-specific setting first
        if service_name:
            service = service_name.upper()
            setting_name = f"{provider}_{service}_TEMPERATURE"
            temperature = getattr(settings, setting_name, None)
            if temperature is not None:
                return float(temperature)

        # Default temperature
        return 0.3

    @staticmethod
    def get_provider_config(
        provider_name: str, service_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get complete configuration for a provider and service.

        Args:
            provider_name: Provider name
            service_name: Optional service name

        Returns:
            Configuration dictionary

        Raises:
            ConfigurationError: If API key is missing
        """
        api_key = AIServicesConfig.get_api_key(provider_name)
        if not api_key:
            raise ConfigurationError(
                f"No API key configured for provider '{provider_name}'. "
                f"Please set {provider_name.upper()}_API_KEY in settings."
            )

        return {
            "api_key": api_key,
            "model": AIServicesConfig.get_model(provider_name, service_name),
            "max_tokens": AIServicesConfig.get_max_tokens(provider_name, service_name),
            "temperature": AIServicesConfig.get_temperature(
                provider_name, service_name
            ),
        }

    @staticmethod
    def validate_provider(provider_name: str) -> bool:
        """
        Validate that a provider is properly configured.

        Args:
            provider_name: Provider name

        Returns:
            True if valid, False otherwise
        """
        try:
            api_key = AIServicesConfig.get_api_key(provider_name)
            return bool(api_key)
        except ConfigurationError:
            return False
