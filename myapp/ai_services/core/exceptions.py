"""
Exception hierarchy for AI services.

Provides unified exception handling across all providers.
"""


class AIServiceError(Exception):
    """Base exception for all AI service errors"""

    pass


class ProviderError(AIServiceError):
    """Base exception for provider-specific errors"""

    pass


class APIError(ProviderError):
    """
    API communication error.

    Raised when communication with the AI provider fails.
    This could be due to network issues, invalid API keys, or server errors.
    """

    pass


class RateLimitError(ProviderError):
    """
    Rate limit exceeded error.

    Raised when the provider's rate limits are exceeded.
    Services should implement retry logic with exponential backoff.
    """

    pass


class ValidationError(AIServiceError):
    """
    Input validation error.

    Raised when input to a service or provider is invalid.
    Examples: content too long, missing required fields, invalid format.
    """

    pass


class ConfigurationError(AIServiceError):
    """
    Configuration error.

    Raised when the service is misconfigured.
    Examples: missing API key, invalid provider name, unsupported model.
    """

    pass


class ProviderNotFoundError(AIServiceError):
    """
    Provider not found error.

    Raised when attempting to use a provider that hasn't been registered.
    """

    pass


class ResponseParsingError(AIServiceError):
    """
    Response parsing error.

    Raised when the provider's response cannot be parsed.
    Examples: invalid JSON, missing required fields, unexpected format.
    """

    pass
