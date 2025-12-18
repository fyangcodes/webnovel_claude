"""
Gemini provider implementation.

Adapts the Google Gemini API to the unified provider interface.
"""

import logging
from typing import List, Optional, Dict, Any

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from ai_services.core import (
    BaseAIProvider,
    ChatMessage,
    ChatCompletionResponse,
    APIError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class GeminiProvider(BaseAIProvider):
    """
    Google Gemini API provider implementation.

    Wraps the Gemini API and provides a unified interface.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp", **kwargs):
        """
        Initialize Gemini provider.

        Args:
            api_key: Gemini API key
            model: Model name (e.g., "gemini-2.0-flash-exp", "gemini-pro")
            **kwargs: Additional Gemini-specific configuration
        """
        self.api_key = api_key
        self.model_name = model
        self.kwargs = kwargs

        # Configure Gemini with API key
        genai.configure(api_key=api_key)

        # Initialize model
        self.model = genai.GenerativeModel(model)

        logger.debug(f"Initialized GeminiProvider with model={model}")

    def chat_completion(
        self,
        messages: List[ChatMessage],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        response_format: Optional[str] = None,
        **kwargs,
    ) -> ChatCompletionResponse:
        """
        Generate completion using Gemini API.

        Args:
            messages: List of ChatMessage objects
            max_tokens: Maximum tokens in response
            temperature: Randomness (0.0-1.0)
            response_format: "json" or "text" (None defaults to text)
            **kwargs: Additional Gemini-specific parameters

        Returns:
            ChatCompletionResponse with unified structure

        Raises:
            APIError: On API communication errors
            RateLimitError: On rate limit exceeded
        """
        # Build generation config
        generation_config = {}

        if max_tokens is not None:
            generation_config["max_output_tokens"] = max_tokens
        if temperature is not None:
            generation_config["temperature"] = temperature
        if response_format == "json":
            generation_config["response_mime_type"] = "application/json"

        # Merge additional kwargs
        generation_config.update(kwargs)

        # Separate system messages from chat history
        # Gemini handles system instructions separately
        system_instructions = []
        chat_history = []

        for msg in messages:
            if msg.role == "system":
                system_instructions.append(msg.content)
            else:
                # Map "user" and "assistant" to Gemini roles
                # Gemini uses "user" and "model" instead of "assistant"
                gemini_role = "user" if msg.role == "user" else "model"
                chat_history.append({"role": gemini_role, "parts": [msg.content]})

        try:
            # Create model with system instruction if present
            if system_instructions:
                model = genai.GenerativeModel(
                    self.model_name,
                    system_instruction="\n".join(system_instructions),
                )
            else:
                model = self.model

            logger.debug(f"Calling Gemini API with model={self.model_name}")

            # Generate response
            if len(chat_history) > 1:
                # Multi-turn conversation: use chat with history
                *history, last_message = chat_history
                chat = model.start_chat(history=history if history else None)
                response = chat.send_message(
                    last_message["parts"][0],
                    generation_config=generation_config,
                    # Disable safety filters for content generation
                    safety_settings={
                        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                    },
                )
            elif chat_history:
                # Single message: use generate_content
                response = model.generate_content(
                    chat_history[0]["parts"][0],
                    generation_config=generation_config,
                    safety_settings={
                        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                    },
                )
            else:
                raise APIError("No messages provided to Gemini")

            # Check if response was blocked
            if not response.candidates:
                raise APIError("Gemini blocked the response (safety filters)")

            # Get response text
            if not response.text:
                raise APIError("Empty response from Gemini")

            # Convert to unified response format
            unified_response = ChatCompletionResponse(
                content=response.text,
                model=self.model_name,
                provider="gemini",
                finish_reason=response.candidates[0].finish_reason.name
                if response.candidates
                else "stop",
                usage={
                    "prompt_tokens": response.usage_metadata.prompt_token_count
                    if hasattr(response, "usage_metadata")
                    else 0,
                    "completion_tokens": response.usage_metadata.candidates_token_count
                    if hasattr(response, "usage_metadata")
                    else 0,
                },
                raw_response=response,
            )

            logger.debug(
                f"Gemini API call successful: {unified_response.total_tokens} tokens"
            )
            return unified_response

        except Exception as e:
            error_msg = str(e).lower()

            # Check for rate limit/quota errors
            if (
                "quota" in error_msg
                or "rate" in error_msg
                or "resource exhausted" in error_msg
            ):
                logger.warning(f"Gemini rate limit/quota exceeded: {e}")
                raise RateLimitError(f"Gemini rate limit exceeded: {e}")

            # Check for authentication errors
            if "api key" in error_msg or "authentication" in error_msg:
                logger.error(f"Gemini authentication error: {e}")
                raise APIError(f"Gemini authentication error: {e}")

            # Generic API error
            logger.error(f"Gemini API error: {e}")
            raise APIError(f"Gemini API error: {e}")

    def validate_settings(self) -> bool:
        """
        Validate Gemini settings.

        Returns:
            True if API key is configured
        """
        return bool(self.api_key)

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get Gemini model information.

        Returns:
            Dictionary with model configuration
        """
        return {
            "provider": "gemini",
            "model": self.model_name,
            "api_version": "v1",
        }
