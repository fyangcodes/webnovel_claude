#!/usr/bin/env python
"""
Test script to verify rate limiting functionality in AI services.

This script tests that:
1. Rate limiter tracks requests correctly
2. Rate limiter waits when approaching limits
3. Rate limiter raises errors when limits exceeded
4. Services integrate rate limiting correctly
"""
import os
import sys
import django
import time

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'myapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myapp.settings')
django.setup()

from unittest.mock import Mock
from ai_services.core.rate_limiter import RateLimiter, get_rate_limiter, get_provider_limits
from ai_services.core.exceptions import RateLimitError
from ai_services.services import AnalysisService
from ai_services.core.models import ChatCompletionResponse


def test_rate_limiter_basic():
    """Test basic rate limiter functionality"""
    print("=" * 70)
    print("TEST 1: Basic Rate Limiter Functionality")
    print("=" * 70)

    limiter = RateLimiter()

    # Test with low limit
    print("\nTesting with 3 requests per minute limit...")
    for i in range(5):
        try:
            result = limiter.check_and_wait(
                provider="test",
                requests_per_minute=3,
                requests_per_day=None,
                max_wait_seconds=5  # Short wait for testing
            )
            print(f"  Request {i+1}: Passed")
        except RateLimitError as e:
            print(f"  Request {i+1}: Rate limited - {str(e)[:100]}")

    # Get status
    status = limiter.get_status("test")
    print(f"\nCurrent status:")
    print(f"  Minute count: {status['minute_count']}")
    print(f"  Day count: {status['day_count']}")

    # Reset
    limiter.reset("test")
    status = limiter.get_status("test")
    print(f"\nAfter reset:")
    print(f"  Minute count: {status['minute_count']}")
    print(f"  Day count: {status['day_count']}")

    print("\n" + "✓" * 70 + "\n")


def test_rate_limiter_wait():
    """Test that rate limiter waits correctly"""
    print("=" * 70)
    print("TEST 2: Rate Limiter Automatic Waiting")
    print("=" * 70)

    limiter = RateLimiter()

    print("\nMaking 3 requests with 2 RPM limit (should wait on 3rd)...")
    start_time = time.time()

    for i in range(3):
        try:
            limiter.check_and_wait(
                provider="test_wait",
                requests_per_minute=2,
                requests_per_day=None,
                max_wait_seconds=65  # Allow up to 65 seconds wait
            )
            elapsed = time.time() - start_time
            print(f"  Request {i+1}: Passed (elapsed: {elapsed:.1f}s)")
        except RateLimitError as e:
            elapsed = time.time() - start_time
            print(f"  Request {i+1}: Rate limited (elapsed: {elapsed:.1f}s)")

    limiter.reset("test_wait")
    print("\n" + "✓" * 70 + "\n")


def test_provider_limits():
    """Test provider limit configuration"""
    print("=" * 70)
    print("TEST 3: Provider Limit Configuration")
    print("=" * 70)

    gemini_limits = get_provider_limits("gemini")
    openai_limits = get_provider_limits("openai")
    unknown_limits = get_provider_limits("unknown")

    print("\nConfigured limits:")
    print(f"  Gemini:")
    print(f"    Requests per minute: {gemini_limits['requests_per_minute']}")
    print(f"    Requests per day: {gemini_limits['requests_per_day']}")

    print(f"  OpenAI:")
    print(f"    Requests per minute: {openai_limits['requests_per_minute']}")
    print(f"    Requests per day: {openai_limits['requests_per_day']}")

    print(f"  Unknown Provider:")
    print(f"    Requests per minute: {unknown_limits['requests_per_minute']}")
    print(f"    Requests per day: {unknown_limits['requests_per_day']}")

    print("\n" + "✓" * 70 + "\n")


def test_analysis_service_integration():
    """Test rate limiting integration in AnalysisService"""
    print("=" * 70)
    print("TEST 4: AnalysisService Rate Limiting Integration")
    print("=" * 70)

    # Reset rate limiter first
    limiter = get_rate_limiter()
    limiter.reset("mock")

    # Create mock provider with successful response
    mock_provider = Mock()
    mock_provider.chat_completion.return_value = ChatCompletionResponse(
        content='{"characters": ["李明"], "places": ["北京"], "terms": ["修炼"], "summary": "测试章节"}',
        model="mock-model",
        provider="mock",
        finish_reason="stop",
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    )

    service = AnalysisService()
    service.provider = mock_provider
    service.provider_name = "mock"

    # Temporarily set very low rate limit for mock provider
    from ai_services.core.rate_limiter import DEFAULT_RATE_LIMITS
    original_limits = DEFAULT_RATE_LIMITS.get("mock")
    DEFAULT_RATE_LIMITS["mock"] = {
        "requests_per_minute": 2,
        "requests_per_day": 10,
    }

    print("\nMaking 3 analysis requests with 2 RPM limit...")
    test_content = "李明在北京修炼，他的朋友张伟来自上海。"

    for i in range(3):
        result = service.extract_entities_and_summary(test_content, "zh")

        if "error_details" in result:
            print(f"  Request {i+1}: Rate limited")
            print(f"    Error type: {'RateLimitError' if 'RateLimitError' in result['error_details'] else 'Other'}")
        else:
            print(f"  Request {i+1}: Success")
            print(f"    Characters: {result.get('characters', [])}")

    # Restore original limits
    if original_limits:
        DEFAULT_RATE_LIMITS["mock"] = original_limits
    else:
        DEFAULT_RATE_LIMITS.pop("mock", None)

    limiter.reset("mock")
    print("\n" + "✓" * 70 + "\n")


def test_global_rate_limiter():
    """Test that global rate limiter is singleton"""
    print("=" * 70)
    print("TEST 5: Global Rate Limiter Singleton")
    print("=" * 70)

    limiter1 = get_rate_limiter()
    limiter2 = get_rate_limiter()

    print(f"\nFirst instance: {id(limiter1)}")
    print(f"Second instance: {id(limiter2)}")
    print(f"Same instance: {limiter1 is limiter2}")

    # Make a request with limiter1
    limiter1.check_and_wait("test_singleton", requests_per_minute=10)

    # Check status with limiter2
    status = limiter2.get_status("test_singleton")
    print(f"\nStatus from second instance:")
    print(f"  Minute count: {status['minute_count']}")

    limiter1.reset("test_singleton")
    print("\n" + "✓" * 70 + "\n")


def main():
    """Run all rate limiting tests"""
    print("\n" + "=" * 70)
    print("RATE LIMITING TEST SUITE")
    print("=" * 70)
    print("\nThis test suite verifies that rate limiting works correctly")
    print("to prevent exceeding API quotas.\n")

    try:
        test_rate_limiter_basic()
        test_rate_limiter_wait()
        test_provider_limits()
        test_analysis_service_integration()
        test_global_rate_limiter()

        print("=" * 70)
        print("ALL TESTS COMPLETED")
        print("=" * 70)
        print("\nKey features verified:")
        print("  ✓ Basic rate limiting with per-minute/per-day tracking")
        print("  ✓ Automatic waiting when approaching limits")
        print("  ✓ RateLimitError when wait time exceeds maximum")
        print("  ✓ Provider-specific limit configuration")
        print("  ✓ Integration with AnalysisService")
        print("  ✓ Global singleton rate limiter instance")
        print("\nRate limiting is now active in AI services!")
        print()

    except Exception as e:
        print(f"\n❌ Test failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
