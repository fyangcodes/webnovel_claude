"""
Base AI service class with shared initialization and configuration.
"""

import logging
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)


class BaseAIService:
    """
    Base class for AI-powered services (translation, analysis, etc.)

    Provides common initialization, OpenAI client setup, and configuration
    management for services that use AI models.
    """

    def __init__(self, model=None, max_tokens=None, temperature=None):
        """
        Initialize the AI service with OpenAI client and configuration.

        Args:
            model (str, optional): AI model to use. If None, uses subclass default.
            max_tokens (int, optional): Maximum tokens for responses. If None, uses subclass default.
            temperature (float, optional): Temperature for AI responses. If None, uses subclass default.

        Raises:
            ValueError: If OpenAI API key is not configured
        """
        # Validate API key
        if not settings.OPENAI_API_KEY:
            raise ValueError("OpenAI API key is not configured in settings")

        # Initialize OpenAI client
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # Set model configuration (allow override or use defaults)
        self.model = model or self._get_default_model()
        self.max_tokens = max_tokens or self._get_default_max_tokens()
        self.temperature = temperature or self._get_default_temperature()

        logger.debug(
            f"Initialized {self.__class__.__name__} with model={self.model}, "
            f"max_tokens={self.max_tokens}, temperature={self.temperature}"
        )

    def _get_default_model(self):
        """
        Get default model for this service.
        Subclasses should override or set MODEL_SETTING_NAME.

        Returns:
            str: Default model name
        """
        model_setting = getattr(self, 'MODEL_SETTING_NAME', None)
        if model_setting:
            return getattr(settings, model_setting, settings.AI_MODEL)
        return settings.AI_MODEL

    def _get_default_max_tokens(self):
        """
        Get default max tokens for this service.
        Subclasses should override or set MAX_TOKENS_SETTING_NAME.

        Returns:
            int: Default max tokens
        """
        max_tokens_setting = getattr(self, 'MAX_TOKENS_SETTING_NAME', None)
        if max_tokens_setting:
            return getattr(settings, max_tokens_setting, 4000)
        return 4000

    def _get_default_temperature(self):
        """
        Get default temperature for this service.
        Subclasses should override or set TEMPERATURE_SETTING_NAME.

        Returns:
            float: Default temperature
        """
        temperature_setting = getattr(self, 'TEMPERATURE_SETTING_NAME', None)
        if temperature_setting:
            return getattr(settings, temperature_setting, 0.3)
        return 0.3

    def _validate_settings(self, required_settings=None):
        """
        Validate that required settings are present.

        Args:
            required_settings (list, optional): List of required setting names to validate

        Raises:
            ValueError: If any required settings are missing
        """
        if required_settings is None:
            required_settings = []

        missing_settings = []
        for setting in required_settings:
            if not hasattr(settings, setting) or not getattr(settings, setting):
                missing_settings.append(setting)

        if missing_settings:
            raise ValueError(
                f"Missing required settings: {', '.join(missing_settings)}"
            )
