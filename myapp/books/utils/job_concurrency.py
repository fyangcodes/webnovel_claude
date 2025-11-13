"""
Job concurrency control utilities.

This module provides Redis-based semaphore mechanisms to control
concurrent job processing across different job types with both
individual and global limits.
"""

import logging
from contextlib import contextmanager
from typing import Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class JobConcurrencyManager:
    """
    Manages job concurrency using Redis-based locks and counters.

    Enforces both:
    1. Global limit across all job types (e.g., max 6 total jobs)
    2. Individual limits per job type (e.g., max 1 translation, 3 analysis, 3 extraction)
    """

    # Redis key prefixes
    GLOBAL_COUNTER_KEY = "job_concurrency:global:count"
    TYPE_COUNTER_KEY_PREFIX = "job_concurrency:type:"
    LOCK_TIMEOUT = 300  # 5 minutes - longer than typical job processing

    def __init__(self):
        self.global_limit = settings.JOB_PROCESSING_GLOBAL_LIMIT
        self.type_limits = {
            'translation': settings.JOB_PROCESSING_TRANSLATION_LIMIT,
            'analysis': settings.JOB_PROCESSING_ANALYSIS_LIMIT,
            'extraction': settings.JOB_PROCESSING_EXTRACTION_LIMIT,
        }

    def _get_type_counter_key(self, job_type: str) -> str:
        """Get Redis key for job type counter."""
        return f"{self.TYPE_COUNTER_KEY_PREFIX}{job_type}:count"

    def _get_global_count(self) -> int:
        """Get current global running job count."""
        count = cache.get(self.GLOBAL_COUNTER_KEY, 0)
        return int(count) if count else 0

    def _get_type_count(self, job_type: str) -> int:
        """Get current running job count for specific type."""
        key = self._get_type_counter_key(job_type)
        count = cache.get(key, 0)
        return int(count) if count else 0

    def _increment_counters(self, job_type: str) -> None:
        """Increment both global and type-specific counters."""
        # Increment global counter
        current_global = self._get_global_count()
        cache.set(self.GLOBAL_COUNTER_KEY, current_global + 1, timeout=self.LOCK_TIMEOUT)

        # Increment type counter
        type_key = self._get_type_counter_key(job_type)
        current_type = self._get_type_count(job_type)
        cache.set(type_key, current_type + 1, timeout=self.LOCK_TIMEOUT)

        logger.debug(
            f"Incremented {job_type} counter: type={current_type + 1}, global={current_global + 1}"
        )

    def _decrement_counters(self, job_type: str) -> None:
        """Decrement both global and type-specific counters."""
        # Decrement global counter
        current_global = self._get_global_count()
        new_global = max(0, current_global - 1)
        cache.set(self.GLOBAL_COUNTER_KEY, new_global, timeout=self.LOCK_TIMEOUT)

        # Decrement type counter
        type_key = self._get_type_counter_key(job_type)
        current_type = self._get_type_count(job_type)
        new_type = max(0, current_type - 1)
        cache.set(type_key, new_type, timeout=self.LOCK_TIMEOUT)

        logger.debug(
            f"Decremented {job_type} counter: type={new_type}, global={new_global}"
        )

    def can_acquire_slot(self, job_type: str) -> bool:
        """
        Check if a job slot can be acquired for the given job type.

        Args:
            job_type: One of 'translation', 'analysis', 'extraction'

        Returns:
            bool: True if both global and type limits allow new job
        """
        if job_type not in self.type_limits:
            logger.error(f"Unknown job type: {job_type}")
            return False

        current_global = self._get_global_count()
        current_type = self._get_type_count(job_type)

        type_limit = self.type_limits[job_type]

        # Check both limits
        can_acquire = (
            current_global < self.global_limit and
            current_type < type_limit
        )

        if not can_acquire:
            logger.debug(
                f"Cannot acquire {job_type} slot: "
                f"global={current_global}/{self.global_limit}, "
                f"type={current_type}/{type_limit}"
            )

        return can_acquire

    def get_available_slots(self, job_type: str) -> int:
        """
        Calculate how many slots are available for the given job type.

        Returns the minimum of:
        - Remaining global slots
        - Remaining type-specific slots

        Args:
            job_type: One of 'translation', 'analysis', 'extraction'

        Returns:
            int: Number of available slots (0 if none available)
        """
        if job_type not in self.type_limits:
            return 0

        current_global = self._get_global_count()
        current_type = self._get_type_count(job_type)

        global_remaining = max(0, self.global_limit - current_global)
        type_remaining = max(0, self.type_limits[job_type] - current_type)

        return min(global_remaining, type_remaining)

    @contextmanager
    def acquire_slot(self, job_type: str):
        """
        Context manager to acquire and release a job slot.

        Usage:
            manager = JobConcurrencyManager()
            with manager.acquire_slot('translation'):
                # Process job here
                pass

        Args:
            job_type: One of 'translation', 'analysis', 'extraction'

        Raises:
            ValueError: If slot cannot be acquired or job_type is invalid
        """
        if not self.can_acquire_slot(job_type):
            raise ValueError(
                f"Cannot acquire slot for {job_type} job: limits reached"
            )

        # Acquire slot
        self._increment_counters(job_type)

        try:
            yield
        finally:
            # Always release slot, even if job fails
            self._decrement_counters(job_type)

    def get_status(self) -> dict:
        """
        Get current concurrency status for monitoring.

        Returns:
            dict: Current counts and limits for all job types
        """
        return {
            'global': {
                'current': self._get_global_count(),
                'limit': self.global_limit,
            },
            'translation': {
                'current': self._get_type_count('translation'),
                'limit': self.type_limits['translation'],
            },
            'analysis': {
                'current': self._get_type_count('analysis'),
                'limit': self.type_limits['analysis'],
            },
            'extraction': {
                'current': self._get_type_count('extraction'),
                'limit': self.type_limits['extraction'],
            },
        }
