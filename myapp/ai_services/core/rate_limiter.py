"""
Rate limiter for AI providers to avoid hitting API quotas.

Implements token bucket algorithm with per-provider limits.
"""
import time
import threading
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for AI API calls.

    Tracks requests per minute and per day to stay within provider quotas.
    """

    def __init__(self):
        self._locks: Dict[str, threading.Lock] = {}
        self._minute_counts: Dict[str, list] = {}  # [(timestamp, count), ...]
        self._day_counts: Dict[str, list] = {}
        self._lock = threading.Lock()

    def _get_provider_lock(self, provider: str) -> threading.Lock:
        """Get or create lock for provider"""
        with self._lock:
            if provider not in self._locks:
                self._locks[provider] = threading.Lock()
            return self._locks[provider]

    def _cleanup_old_entries(self, entries: list, max_age_seconds: int) -> list:
        """Remove entries older than max_age_seconds"""
        now = time.time()
        cutoff = now - max_age_seconds
        return [entry for entry in entries if entry[0] > cutoff]

    def check_and_wait(
        self,
        provider: str,
        requests_per_minute: Optional[int] = None,
        requests_per_day: Optional[int] = None,
        max_wait_seconds: int = 120
    ) -> bool:
        """
        Check rate limits and wait if necessary.

        Args:
            provider: Provider name (e.g., "openai", "gemini")
            requests_per_minute: Max requests per minute (None = no limit)
            requests_per_day: Max requests per day (None = no limit)
            max_wait_seconds: Maximum time to wait before giving up

        Returns:
            True if request can proceed, False if wait time exceeded max

        Raises:
            RateLimitError: If cannot proceed within max_wait_seconds
        """
        from ai_services.core.exceptions import RateLimitError

        lock = self._get_provider_lock(provider)

        with lock:
            now = time.time()

            # Initialize tracking for this provider
            if provider not in self._minute_counts:
                self._minute_counts[provider] = []
            if provider not in self._day_counts:
                self._day_counts[provider] = []

            # Cleanup old entries
            self._minute_counts[provider] = self._cleanup_old_entries(
                self._minute_counts[provider], 60  # 1 minute
            )
            self._day_counts[provider] = self._cleanup_old_entries(
                self._day_counts[provider], 86400  # 24 hours
            )

            # Check if we can proceed
            wait_time = 0

            # Check per-minute limit
            if requests_per_minute is not None:
                current_minute_count = len(self._minute_counts[provider])
                if current_minute_count >= requests_per_minute:
                    # Find when the oldest request will expire
                    oldest_timestamp = self._minute_counts[provider][0][0]
                    time_until_available = (oldest_timestamp + 60) - now
                    wait_time = max(wait_time, time_until_available)

            # Check per-day limit
            if requests_per_day is not None:
                current_day_count = len(self._day_counts[provider])
                if current_day_count >= requests_per_day:
                    # Find when the oldest request will expire
                    oldest_timestamp = self._day_counts[provider][0][0]
                    time_until_available = (oldest_timestamp + 86400) - now
                    wait_time = max(wait_time, time_until_available)

            # If we need to wait
            if wait_time > 0:
                if wait_time > max_wait_seconds:
                    logger.error(
                        f"{provider} rate limit exceeded. Would need to wait "
                        f"{wait_time:.1f}s (max: {max_wait_seconds}s)"
                    )
                    raise RateLimitError(
                        f"{provider} rate limit exceeded. Please wait {wait_time:.1f} seconds or "
                        f"consider upgrading your API plan."
                    )

                logger.warning(
                    f"{provider} rate limit approaching. Waiting {wait_time:.1f}s..."
                )
                time.sleep(wait_time + 0.1)  # Add small buffer

            # Record this request
            self._minute_counts[provider].append((now, 1))
            self._day_counts[provider].append((now, 1))

            logger.debug(
                f"{provider} rate check passed. "
                f"Minute: {len(self._minute_counts[provider])}/{requests_per_minute or '∞'}, "
                f"Day: {len(self._day_counts[provider])}/{requests_per_day or '∞'}"
            )

            return True

    def get_status(self, provider: str) -> Dict:
        """
        Get current rate limit status for a provider.

        Args:
            provider: Provider name

        Returns:
            Dict with current counts and limits
        """
        lock = self._get_provider_lock(provider)

        with lock:
            if provider not in self._minute_counts:
                return {
                    "minute_count": 0,
                    "day_count": 0,
                    "minute_remaining": "unknown",
                    "day_remaining": "unknown"
                }

            # Cleanup old entries
            self._minute_counts[provider] = self._cleanup_old_entries(
                self._minute_counts[provider], 60
            )
            self._day_counts[provider] = self._cleanup_old_entries(
                self._day_counts[provider], 86400
            )

            return {
                "minute_count": len(self._minute_counts[provider]),
                "day_count": len(self._day_counts[provider]),
            }

    def reset(self, provider: Optional[str] = None):
        """
        Reset rate limiter for a provider or all providers.

        Args:
            provider: Provider name, or None to reset all
        """
        with self._lock:
            if provider:
                self._minute_counts.pop(provider, None)
                self._day_counts.pop(provider, None)
                logger.info(f"Reset rate limiter for {provider}")
            else:
                self._minute_counts.clear()
                self._day_counts.clear()
                logger.info("Reset rate limiter for all providers")


# Global rate limiter instance
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance"""
    return _rate_limiter


# Default rate limits for different providers (free tier)
DEFAULT_RATE_LIMITS = {
    "gemini": {
        "requests_per_minute": 4,   # Conservative limit for gemini-2.5-flash free tier (actual: 5 RPM)
        "requests_per_day": 1500,   # Daily limit for free tier
    },
    "openai": {
        "requests_per_minute": 60,  # Tier 1 limit
        "requests_per_day": None,   # No daily limit on Tier 1+
    },
}


def get_provider_limits(provider: str) -> Dict:
    """
    Get rate limits for a provider.

    Args:
        provider: Provider name

    Returns:
        Dict with requests_per_minute and requests_per_day
    """
    return DEFAULT_RATE_LIMITS.get(
        provider.lower(),
        {"requests_per_minute": None, "requests_per_day": None}
    )
