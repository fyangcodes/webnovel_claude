# AI Services Rate Limiting

## Overview

The AI services implement intelligent rate limiting to prevent exceeding API provider quotas. This prevents errors like "quota exceeded" and ensures smooth operation within free tier or paid tier limits.

## Architecture

### Components

1. **RateLimiter Class** (`ai_services/core/rate_limiter.py`)
   - Thread-safe token bucket algorithm
   - Tracks requests per minute and per day
   - Per-provider tracking (separate limits for OpenAI, Gemini, etc.)
   - Automatic waiting when approaching limits

2. **Provider Limits Configuration** (`ai_services/core/rate_limiter.py`)
   - Default limits for each provider
   - Easy to adjust for different API tiers
   - Supports unlimited limits (None value)

3. **Service Integration**
   - AnalysisService: Rate limit check before entity extraction
   - TranslationService: Rate limit check before translation API calls
   - Automatic error handling with detailed logging

## Default Rate Limits

### Gemini (Free Tier)
```python
{
    "requests_per_minute": 15,  # Conservative limit
    "requests_per_day": 1500,   # Daily quota
}
```

### OpenAI (Tier 1)
```python
{
    "requests_per_minute": 60,  # Tier 1 limit
    "requests_per_day": None,   # No daily limit on Tier 1+
}
```

## How It Works

### Token Bucket Algorithm

1. **Request Tracking**: Each API call is recorded with a timestamp
2. **Old Entry Cleanup**: Entries older than the time window are removed
3. **Limit Check**: Current count is compared against limits
4. **Wait Calculation**: If limit reached, calculates how long to wait
5. **Automatic Waiting**: Sleeps if wait time is under max_wait_seconds
6. **Error on Exceed**: Raises RateLimitError if wait time exceeds maximum

### Flow Diagram

```
┌─────────────────────────────────────────┐
│  Service calls extract_entities() or    │
│  translate_chapter()                    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Get rate limiter and provider limits   │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  rate_limiter.check_and_wait()          │
│  - Clean up old entries                 │
│  - Check per-minute count               │
│  - Check per-day count                  │
└────────────────┬────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
┌──────────────┐   ┌─────────────────┐
│ Within Limit │   │ Limit Exceeded  │
└──────┬───────┘   └────────┬────────┘
       │                    │
       │                    ▼
       │           ┌──────────────────┐
       │           │ Calculate Wait   │
       │           └────────┬─────────┘
       │                    │
       │           ┌────────┴────────┐
       │           │                 │
       │           ▼                 ▼
       │    ┌──────────────┐  ┌─────────────┐
       │    │ Wait < 120s  │  │ Wait > 120s │
       │    └──────┬───────┘  └──────┬──────┘
       │           │                 │
       │           ▼                 ▼
       │    ┌──────────────┐  ┌─────────────┐
       │    │ Sleep & Retry│  │ Raise Error │
       │    └──────┬───────┘  └─────────────┘
       │           │
       └───────────┴──────────────────┐
                                      ▼
                          ┌───────────────────────┐
                          │ Proceed with API Call │
                          └───────────────────────┘
```

## Usage Examples

### Basic Usage (Automatic)

Rate limiting is **automatically applied** in all AI service calls:

```python
from ai_services.services import AnalysisService, TranslationService

# Analysis - rate limiting happens automatically
service = AnalysisService()
result = service.extract_entities_and_summary(content, "zh")

# Translation - rate limiting happens automatically
translation_service = TranslationService()
translated = translation_service.translate_chapter(chapter, "en")
```

### Manual Usage

You can also use the rate limiter directly:

```python
from ai_services.core.rate_limiter import get_rate_limiter, get_provider_limits

rate_limiter = get_rate_limiter()
limits = get_provider_limits("gemini")

# Check and wait if needed
try:
    rate_limiter.check_and_wait(
        provider="gemini",
        requests_per_minute=limits['requests_per_minute'],
        requests_per_day=limits['requests_per_day'],
        max_wait_seconds=120
    )
    # Proceed with API call
except RateLimitError as e:
    print(f"Rate limit exceeded: {e}")
```

### Get Current Status

```python
from ai_services.core.rate_limiter import get_rate_limiter

rate_limiter = get_rate_limiter()
status = rate_limiter.get_status("gemini")

print(f"Current minute: {status['minute_count']} requests")
print(f"Current day: {status['day_count']} requests")
```

### Reset Rate Limiter

```python
from ai_services.core.rate_limiter import get_rate_limiter

rate_limiter = get_rate_limiter()

# Reset specific provider
rate_limiter.reset("gemini")

# Reset all providers
rate_limiter.reset()
```

## Configuration

### Adjusting Limits

Edit `myapp/ai_services/core/rate_limiter.py`:

```python
DEFAULT_RATE_LIMITS = {
    "gemini": {
        "requests_per_minute": 15,  # Adjust this
        "requests_per_day": 1500,   # Adjust this
    },
    "openai": {
        "requests_per_minute": 60,  # Adjust this
        "requests_per_day": None,   # None = no limit
    },
}
```

### Environment-Based Configuration

You can also configure limits via settings.py:

```python
# myapp/myapp/settings.py

AI_RATE_LIMITS = {
    "gemini": {
        "requests_per_minute": int(os.getenv("GEMINI_RPM", "15")),
        "requests_per_day": int(os.getenv("GEMINI_RPD", "1500")),
    },
    "openai": {
        "requests_per_minute": int(os.getenv("OPENAI_RPM", "60")),
        "requests_per_day": None,  # OpenAI typically has no daily limit
    },
}
```

Then in `.env`:
```bash
GEMINI_RPM=20
GEMINI_RPD=2000
OPENAI_RPM=90
```

## Error Handling

### RateLimitError Format

When rate limit is exceeded, detailed error information is captured:

```
=== Analysis Error Details ===
Error Type: RateLimitError
Error Message: gemini rate limit exceeded. Please wait 45.3 seconds or consider upgrading your API plan.
Provider: gemini
Model: gemini-1.5-flash

--- Content Preview (first 500 chars) ---
李明在北京修炼，他的朋友张伟来自上海...

--- Prompt Sent ---
Extract entities from the following Chinese text...

--- Response Received ---
(No response received)

=== End Error Details ===
```

### Error in Database

For AnalysisJob:
- Status: `COMPLETED` (with warnings)
- error_message: Contains full error details including rate limit info

For TranslationJob:
- Status: `FAILED`
- error_message: Contains full error details with rate limit info

### Viewing Errors in Django Admin

1. Go to **Django Admin → Books → Analysis Jobs** or **Translation Jobs**
2. Filter by Status: "Failed" or "Completed"
3. Check the "Error message" field for rate limit details
4. Look for "RateLimitError" entries

## Monitoring and Debugging

### Check Current Rate Status

Create a management command to check status:

```python
# myapp/books/management/commands/check_rate_limits.py

from django.core.management.base import BaseCommand
from ai_services.core.rate_limiter import get_rate_limiter, DEFAULT_RATE_LIMITS

class Command(BaseCommand):
    help = "Check current rate limit status for all providers"

    def handle(self, *args, **options):
        rate_limiter = get_rate_limiter()

        for provider, limits in DEFAULT_RATE_LIMITS.items():
            status = rate_limiter.get_status(provider)

            self.stdout.write(f"\n{provider.upper()}:")
            self.stdout.write(f"  Current minute: {status['minute_count']}")
            self.stdout.write(f"  Current day: {status['day_count']}")

            if limits['requests_per_minute']:
                remaining_min = limits['requests_per_minute'] - status['minute_count']
                self.stdout.write(f"  Remaining (minute): {remaining_min}")

            if limits['requests_per_day']:
                remaining_day = limits['requests_per_day'] - status['day_count']
                self.stdout.write(f"  Remaining (day): {remaining_day}")
```

Run with:
```bash
python manage.py check_rate_limits
```

### Log Analysis

Rate limit events are logged at different levels:

- **INFO**: Request passed rate limit check
- **WARNING**: Approaching limit, waiting before request
- **ERROR**: Rate limit exceeded, max wait time exceeded

Check logs:
```bash
# Docker
docker-compose logs web | grep -i "rate"

# Local
tail -f logs/django.log | grep -i "rate"
```

### Reset During Development

If you're testing and want to reset counters:

```python
# Django shell
python manage.py shell

from ai_services.core.rate_limiter import get_rate_limiter
rate_limiter = get_rate_limiter()
rate_limiter.reset("gemini")
```

## Best Practices

### 1. Set Conservative Limits

Always set limits **lower than the actual API quotas** to leave a safety buffer:

```python
# If Gemini free tier is 15 RPM, set to 12-13
"requests_per_minute": 13,  # Leave 2-3 request buffer
```

### 2. Monitor Logs Regularly

Check for rate limit warnings:
- Daily checks in production
- Adjust limits if seeing frequent warnings
- Consider upgrading API plan if hitting limits often

### 3. Use Appropriate max_wait_seconds

- **Analysis Service**: 120 seconds (2 minutes) is reasonable
- **Translation Service**: 120 seconds (2 minutes) is reasonable
- **Interactive APIs**: Lower to 30-60 seconds for better UX

### 4. Handle Errors Gracefully

Services automatically handle rate limits:
- Analysis returns fallback results with error_details
- Translation raises exception with detailed error info
- Both log comprehensively for debugging

### 5. Test Rate Limiting

Test that rate limiting works:

```python
# Test script
from ai_services.services import AnalysisService

service = AnalysisService()

# Make multiple rapid requests
for i in range(20):
    print(f"Request {i+1}")
    result = service.extract_entities_and_summary("测试内容", "zh")
    if "error_details" in result:
        print(f"Rate limited at request {i+1}")
        break
```

### 6. Per-Service Rate Limits

Consider different limits for different services:

```python
# High-volume analysis might need higher limits
analysis_limits = get_provider_limits("gemini")
analysis_limits['requests_per_minute'] = 20  # Adjust

# Lower-volume translation might be fine with defaults
translation_limits = get_provider_limits("gemini")
```

## Troubleshooting

### Issue: Still hitting rate limits

**Possible causes:**
1. Multiple service instances (each has its own rate limiter)
2. Limits set too high
3. Burst traffic exceeding per-minute limits

**Solutions:**
1. Use shared Redis cache for rate limiting across instances
2. Lower the configured limits
3. Implement queue-based processing with rate limiting

### Issue: Services waiting too long

**Possible causes:**
1. Limits set too low
2. High request volume
3. max_wait_seconds too high

**Solutions:**
1. Increase limits if you have higher API tier
2. Implement job queue to handle burst traffic
3. Lower max_wait_seconds and handle errors differently

### Issue: Rate limiter not working

**Possible causes:**
1. Rate limiter not imported correctly
2. Provider name mismatch
3. Limits not configured

**Solutions:**
1. Check imports and ensure using get_rate_limiter()
2. Verify provider_name matches DEFAULT_RATE_LIMITS keys
3. Check that limits are properly configured

## API Reference

### RateLimiter.check_and_wait()

```python
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
        True if request can proceed

    Raises:
        RateLimitError: If cannot proceed within max_wait_seconds
    """
```

### RateLimiter.get_status()

```python
def get_status(self, provider: str) -> Dict:
    """
    Get current rate limit status for a provider.

    Args:
        provider: Provider name

    Returns:
        Dict with keys:
            - minute_count: Current requests in the last minute
            - day_count: Current requests in the last 24 hours
    """
```

### RateLimiter.reset()

```python
def reset(self, provider: Optional[str] = None):
    """
    Reset rate limiter for a provider or all providers.

    Args:
        provider: Provider name, or None to reset all
    """
```

### get_rate_limiter()

```python
def get_rate_limiter() -> RateLimiter:
    """
    Get the global rate limiter instance.

    Returns:
        Singleton RateLimiter instance
    """
```

### get_provider_limits()

```python
def get_provider_limits(provider: str) -> Dict:
    """
    Get rate limits for a provider.

    Args:
        provider: Provider name

    Returns:
        Dict with keys:
            - requests_per_minute: int or None
            - requests_per_day: int or None
    """
```

## Future Enhancements

### Redis-Based Rate Limiting (Multi-Instance)

For production with multiple service instances:

```python
# ai_services/core/redis_rate_limiter.py
import redis
from django.conf import settings

class RedisRateLimiter:
    """Rate limiter using Redis for cross-instance coordination"""

    def __init__(self):
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB
        )

    def check_and_wait(self, provider, requests_per_minute, requests_per_day):
        # Use Redis to track requests across all instances
        pass
```

### Dynamic Limit Adjustment

Automatically adjust limits based on observed errors:

```python
class AdaptiveRateLimiter:
    """Rate limiter that adjusts limits based on API responses"""

    def on_rate_limit_error(self, provider):
        # Reduce limits by 20%
        current = self.limits[provider]['requests_per_minute']
        self.limits[provider]['requests_per_minute'] = int(current * 0.8)
```

### Per-User Rate Limiting

Track rate limits per user for multi-tenant scenarios:

```python
def check_and_wait(self, provider, user_id, ...):
    key = f"{provider}:{user_id}"
    # Track per user instead of globally
```

---

**Last Updated:** 2025-12-18
**Version:** 1.0.0
**Related Documentation:**
- [AI Services Error Handling](AI_SERVICES_ERROR_HANDLING.md)
- [AI Services Architecture](AI_SERVICES_ARCHITECTURE_DIAGRAM.md)
- [Translation Refactoring Plan](TRANSLATION_REFACTORING_PLAN.md)
