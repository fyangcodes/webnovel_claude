"""
Unified data models for AI service communication.

These models provide a provider-agnostic interface for AI interactions,
allowing services to work with any AI provider (OpenAI, Gemini, etc.)
without changing business logic.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ChatMessage:
    """
    Unified chat message format.

    All providers convert to/from this format for consistency.
    """

    role: str  # "system", "user", or "assistant"
    content: str

    def __post_init__(self):
        """Validate role"""
        valid_roles = {"system", "user", "assistant"}
        if self.role not in valid_roles:
            raise ValueError(
                f"Invalid role '{self.role}'. Must be one of: {valid_roles}"
            )


@dataclass
class ChatCompletionResponse:
    """
    Unified completion response format.

    All providers convert their responses to this format.
    """

    content: str  # The actual response text
    model: str  # Model used (e.g., "gpt-4o-mini", "gemini-2.0-flash-exp")
    provider: str  # Provider name (e.g., "openai", "gemini")
    finish_reason: str  # Why the response ended (e.g., "stop", "length")
    usage: Dict[str, int]  # Token usage: {"prompt_tokens": X, "completion_tokens": Y}
    raw_response: Optional[Any] = None  # Provider-specific raw response for debugging

    def __post_init__(self):
        """Validate required fields"""
        if not self.content:
            raise ValueError("Response content cannot be empty")
        if not self.model:
            raise ValueError("Model name is required")
        if not self.provider:
            raise ValueError("Provider name is required")
        if not isinstance(self.usage, dict):
            raise ValueError("Usage must be a dictionary")

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens used"""
        return self.usage.get("prompt_tokens", 0) + self.usage.get(
            "completion_tokens", 0
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding raw_response)"""
        return {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "total_tokens": self.total_tokens,
        }
