"""
Base AI provider interface.

All AI providers must implement this interface to be compatible
with the AI services layer.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

from .models import ChatMessage, ChatCompletionResponse


class BaseAIProvider(ABC):
    """
    Abstract base class for AI providers.

    All providers (OpenAI, Gemini, etc.) must implement these methods
    to be compatible with the service layer.
    """

    @abstractmethod
    def __init__(self, api_key: str, model: str, **kwargs):
        """
        Initialize provider with credentials and configuration.

        Args:
            api_key: API key for authentication
            model: Model identifier (provider-specific)
            **kwargs: Additional provider-specific configuration
        """
        pass

    @abstractmethod
    def chat_completion(
        self,
        messages: List[ChatMessage],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        response_format: Optional[str] = None,
        **kwargs,
    ) -> ChatCompletionResponse:
        """
        Generate chat completion.

        This is the main method that all providers must implement.
        It takes unified ChatMessage objects and returns a unified
        ChatCompletionResponse.

        Args:
            messages: List of chat messages
            max_tokens: Maximum tokens in response (None = provider default)
            temperature: Randomness (0.0-1.0, None = provider default)
            response_format: Expected format ("json" or "text", None = text)
            **kwargs: Additional provider-specific parameters

        Returns:
            ChatCompletionResponse with unified structure

        Raises:
            APIError: On API communication errors
            RateLimitError: On rate limit exceeded
            ValidationError: On invalid input
        """
        pass

    @abstractmethod
    def validate_settings(self) -> bool:
        """
        Validate provider settings and connectivity.

        Can optionally ping the API to verify credentials.

        Returns:
            True if settings are valid, False otherwise
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about current model configuration.

        Returns:
            Dictionary with model information:
            {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "api_version": "v1",
                ...
            }
        """
        pass

    def __repr__(self) -> str:
        """String representation"""
        info = self.get_model_info()
        return f"{self.__class__.__name__}(provider={info.get('provider')}, model={info.get('model')})"
