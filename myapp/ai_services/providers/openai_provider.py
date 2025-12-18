"""
OpenAI provider implementation.

Adapts the OpenAI API to the unified provider interface.
"""

import logging
from typing import List, Optional, Dict, Any

from openai import OpenAI

from ai_services.core import (
    BaseAIProvider,
    ChatMessage,
    ChatCompletionResponse,
    APIError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseAIProvider):
    """
    OpenAI API provider implementation.

    Wraps the OpenAI API and provides a unified interface.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", **kwargs):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model name (e.g., "gpt-4o-mini", "gpt-4", "gpt-3.5-turbo")
            **kwargs: Additional OpenAI-specific configuration
        """
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(api_key=api_key)
        self.kwargs = kwargs

        logger.debug(f"Initialized OpenAIProvider with model={model}")

    def chat_completion(
        self,
        messages: List[ChatMessage],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        response_format: Optional[str] = None,
        **kwargs,
    ) -> ChatCompletionResponse:
        """
        Generate chat completion using OpenAI API.

        Args:
            messages: List of ChatMessage objects
            max_tokens: Maximum tokens in response
            temperature: Randomness (0.0-1.0)
            response_format: "json" or "text" (None defaults to text)
            **kwargs: Additional OpenAI-specific parameters

        Returns:
            ChatCompletionResponse with unified structure

        Raises:
            APIError: On API communication errors
            RateLimitError: On rate limit exceeded
        """
        # Convert unified messages to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        # Build request parameters
        params = {
            "model": self.model,
            "messages": openai_messages,
        }

        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if temperature is not None:
            params["temperature"] = temperature
        if response_format == "json":
            params["response_format"] = {"type": "json_object"}

        # Merge additional kwargs
        params.update(kwargs)

        try:
            logger.debug(f"Calling OpenAI API with model={self.model}")
            response = self.client.chat.completions.create(**params)

            if not response.choices:
                raise APIError("No response choices returned from OpenAI")

            content = response.choices[0].message.content
            if not content:
                raise APIError("Empty content in OpenAI response")

            # Convert to unified response format
            unified_response = ChatCompletionResponse(
                content=content,
                model=response.model,
                provider="openai",
                finish_reason=response.choices[0].finish_reason,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                },
                raw_response=response,
            )

            logger.debug(
                f"OpenAI API call successful: {unified_response.total_tokens} tokens"
            )
            return unified_response

        except Exception as e:
            error_msg = str(e).lower()

            # Check for rate limit errors
            if "rate limit" in error_msg or "rate_limit" in error_msg:
                logger.warning(f"OpenAI rate limit exceeded: {e}")
                raise RateLimitError(f"OpenAI rate limit exceeded: {e}")

            # Check for quota/billing errors
            if "quota" in error_msg or "billing" in error_msg:
                logger.error(f"OpenAI quota/billing error: {e}")
                raise APIError(f"OpenAI quota error: {e}")

            # Check for authentication errors
            if "auth" in error_msg or "api key" in error_msg:
                logger.error(f"OpenAI authentication error: {e}")
                raise APIError(f"OpenAI authentication error: {e}")

            # Generic API error
            logger.error(f"OpenAI API error: {e}")
            raise APIError(f"OpenAI API error: {e}")

    def validate_settings(self) -> bool:
        """
        Validate OpenAI settings.

        Returns:
            True if API key is configured
        """
        return bool(self.api_key)

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get OpenAI model information.

        Returns:
            Dictionary with model configuration
        """
        return {
            "provider": "openai",
            "model": self.model,
            "api_version": "v1",
        }
