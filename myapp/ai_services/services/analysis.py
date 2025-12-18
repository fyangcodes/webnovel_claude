"""
Provider-agnostic analysis service for entity extraction and summarization.
"""

import json
import logging
from typing import Dict, Optional

from ai_services.core import ChatMessage, ValidationError, RateLimitError
from ai_services.core.exceptions import ResponseParsingError
from ai_services.core.rate_limiter import get_rate_limiter, get_provider_limits
from .base_service import BaseAIService
from ai_services.prompts.analysis import AnalysisPromptBuilder

logger = logging.getLogger(__name__)


class AnalysisService(BaseAIService):
    """
    AI-powered analysis service for entity extraction and summarization.

    This service is provider-agnostic and works with any registered provider.
    """

    SERVICE_NAME = "analysis"
    DEFAULT_MAX_TOKENS = 4000  # Increased to ensure complete JSON responses
    DEFAULT_TEMPERATURE = 0.1

    def extract_entities_and_summary(
        self, content: str, language_code: str = "zh"
    ) -> Dict[str, any]:
        """
        Extract entities and summary from content.

        Args:
            content: Text content to analyze
            language_code: Source language code (default: "zh")

        Returns:
            Dict with keys:
                - characters: List[str] - Character names
                - places: List[str] - Place names
                - terms: List[str] - Special terms
                - summary: str - Brief chapter summary
                - error_details: Optional[str] - Detailed error info if parsing failed
        """
        # Build prompt using template
        prompt_builder = AnalysisPromptBuilder()
        prompt = prompt_builder.build(content, language_code)

        # Create message
        messages = [ChatMessage(role="user", content=prompt)]

        response_content = None
        try:
            # Check rate limits before making API call
            rate_limiter = get_rate_limiter()
            limits = get_provider_limits(self.provider_name)

            try:
                rate_limiter.check_and_wait(
                    provider=self.provider_name,
                    requests_per_minute=limits.get('requests_per_minute'),
                    requests_per_day=limits.get('requests_per_day'),
                    max_wait_seconds=120  # Wait up to 2 minutes
                )
            except RateLimitError as e:
                # Rate limit exceeded - record error details
                error_details = self._format_error_details(
                    error_type="RateLimitError",
                    error_message=str(e),
                    prompt=prompt,
                    response=None,
                    content_preview=content[:500]
                )
                logger.error(f"Rate limit exceeded: {e}\n{error_details}")

                result = self._get_fallback_result(content)
                result["error_details"] = error_details
                return result

            # Call provider (agnostic to OpenAI/Gemini)
            response = self.provider.chat_completion(
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format="json",
            )
            response_content = response.content

            # Parse JSON response
            result = self._parse_json_response(response_content)
            self._validate_result(result)
            result = self._clean_entity_names(result)

            logger.info(
                f"Successfully extracted entities via {self.provider_name}: "
                f"{len(result.get('characters', []))} chars, "
                f"{len(result.get('places', []))} places, "
                f"{len(result.get('terms', []))} terms"
            )

            return result

        except (ResponseParsingError, ValidationError) as e:
            # These are validation errors - record detailed error information
            error_details = self._format_error_details(
                error_type=type(e).__name__,
                error_message=str(e),
                prompt=prompt,
                response=response_content,
                content_preview=content[:500]
            )
            logger.error(f"Entity extraction validation failed: {e}\n{error_details}")

            # Return result with error details for storage
            result = self._get_fallback_result(content)
            result["error_details"] = error_details
            return result

        except Exception as e:
            # Other errors (API, network, etc.)
            error_details = self._format_error_details(
                error_type=type(e).__name__,
                error_message=str(e),
                prompt=prompt,
                response=response_content,
                content_preview=content[:500]
            )
            logger.error(f"Entity extraction failed: {e}\n{error_details}")

            result = self._get_fallback_result(content)
            result["error_details"] = error_details
            return result

    def _parse_json_response(self, response_text: str) -> Dict:
        """
        Parse JSON response with cleaning.

        Args:
            response_text: Raw response text

        Returns:
            Parsed JSON dictionary

        Raises:
            ResponseParsingError: If JSON cannot be parsed
        """
        try:
            # Clean the response
            cleaned = self._clean_json_response(response_text)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.debug(f"Raw response: {response_text[:500]}...")
            raise ResponseParsingError(f"Invalid JSON response: {e}")

    def _clean_json_response(self, response_text: str) -> str:
        """
        Clean JSON response by removing markdown code blocks, etc.

        Args:
            response_text: Raw response text

        Returns:
            Cleaned response text
        """
        # Remove markdown code blocks
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        response_text = response_text.strip()

        # Try to find JSON object bounds if there's extra text
        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}")

        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            response_text = response_text[start_idx : end_idx + 1]

        return response_text

    def _validate_result(self, result: Dict) -> None:
        """
        Validate extraction result structure.

        Args:
            result: Parsed result dictionary

        Raises:
            ValidationError: If structure is invalid
        """
        required_keys = ["characters", "places", "terms", "summary"]

        for key in required_keys:
            if key not in result:
                raise ValidationError(f"Missing required key: {key}")

        # Ensure lists are actually lists
        for key in ["characters", "places", "terms"]:
            if not isinstance(result[key], list):
                raise ValidationError(f"{key} must be a list")

        # Ensure summary is string
        if not isinstance(result["summary"], str):
            raise ValidationError("summary must be a string")

    def _clean_entity_names(self, result: Dict) -> Dict:
        """
        Clean entity names by removing decorative punctuation.

        Args:
            result: Result dictionary with entity lists

        Returns:
            Result with cleaned entity names
        """
        # Decorative characters to remove
        decorative_chars = {
            "《": "",
            "》": "",  # Chinese book title markers
            "「": "",
            "」": "",  # Japanese quotes
            "『": "",
            "』": "",  # Japanese double quotes
            """: "",
            """: "",  # Smart quotes
            '"': "",
            "'": "",  # Regular quotes
        }

        for category in ["characters", "places", "terms"]:
            if category in result and isinstance(result[category], list):
                cleaned = []
                for entity in result[category]:
                    if isinstance(entity, str):
                        # Remove decorative characters
                        cleaned_entity = entity
                        for old, new in decorative_chars.items():
                            cleaned_entity = cleaned_entity.replace(old, new)

                        # Strip whitespace
                        cleaned_entity = cleaned_entity.strip()

                        # Only add if non-empty after cleaning
                        if cleaned_entity:
                            cleaned.append(cleaned_entity)

                result[category] = cleaned

        return result

    def _format_error_details(
        self,
        error_type: str,
        error_message: str,
        prompt: str,
        response: Optional[str],
        content_preview: str
    ) -> str:
        """
        Format detailed error information for logging and storage.

        Args:
            error_type: Type of error (class name)
            error_message: Error message
            prompt: The prompt that was sent
            response: The response received (may be None)
            content_preview: Preview of the content being analyzed

        Returns:
            Formatted error details string
        """
        details = []
        details.append(f"=== Analysis Error Details ===")
        details.append(f"Error Type: {error_type}")
        details.append(f"Error Message: {error_message}")
        details.append(f"Provider: {self.provider_name}")
        details.append(f"Model: {getattr(self.provider, 'model', 'unknown')}")
        details.append("")
        details.append(f"--- Content Preview (first 500 chars) ---")
        details.append(content_preview)
        details.append("")
        details.append(f"--- Prompt Sent ---")
        details.append(prompt[:2000] if len(prompt) > 2000 else prompt)
        if len(prompt) > 2000:
            details.append(f"... (prompt truncated, total length: {len(prompt)} chars)")
        details.append("")
        details.append(f"--- Response Received ---")
        if response:
            details.append(response[:2000] if len(response) > 2000 else response)
            if len(response) > 2000:
                details.append(f"... (response truncated, total length: {len(response)} chars)")
        else:
            details.append("(No response received)")
        details.append("")
        details.append(f"=== End Error Details ===")

        return "\n".join(details)

    def _get_fallback_result(self, content: str) -> Dict:
        """
        Return fallback result when AI extraction fails.

        Args:
            content: Original content

        Returns:
            Fallback result with empty lists and truncated summary
        """
        return {
            "characters": [],
            "places": [],
            "terms": [],
            "summary": content[:200] + "..." if len(content) > 200 else content,
        }
