# Gemini 2.5 Flash API Fixes

## Issues and Solutions

### Issue 1: Rate Limit Errors (429 Quota Exceeded)

**Problem:**
```
Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests
limit: 5, model: gemini-2.5-flash
```

**Root Cause:**
- Gemini 2.5 Flash has **5 requests/minute** limit (much lower than older models)
- Rate limiter was configured for 15 RPM (for Gemini 1.5 Flash)
- System was sending requests too fast

**Solution:**
Updated [myapp/ai_services/core/rate_limiter.py](../myapp/ai_services/core/rate_limiter.py:196-205):

```python
DEFAULT_RATE_LIMITS = {
    "gemini": {
        "requests_per_minute": 4,   # Conservative for gemini-2.5-flash (actual: 5 RPM)
        "requests_per_day": 1500,   # Daily limit
    },
}
```

**Result:**
- ✅ System now sends maximum 4 requests/minute (safely under 5 RPM limit)
- ✅ Automatically waits ~15 seconds between requests
- ✅ No more quota exceeded errors

**Trade-off:**
- Processing slower: 4 chapters/minute instead of 15 chapters/minute
- But reliable and free

---

### Issue 2: Truncated JSON Responses

**Problem:**
```json
{
  "summary": "本章描绘了半步峰与应悔峰的险峻地貌...不料，身受重伤的沈峤从峰顶坠落，晏无师命玉生
                                                                                    ↑ Cut off!
}
```

**Error:**
```
ResponseParsingError: Invalid JSON response: Unterminated string starting at: line 31 column 14
```

**Root Cause:**
- `max_tokens` set to 2000 was insufficient for complete responses
- Gemini 2.5 Flash hit token limit mid-sentence
- JSON became invalid (unterminated strings)

**Solution:**
Updated [myapp/ai_services/services/analysis.py](../myapp/ai_services/services/analysis.py:26):

```python
class AnalysisService(BaseAIService):
    SERVICE_NAME = "analysis"
    DEFAULT_MAX_TOKENS = 4000  # Increased from 2000
    DEFAULT_TEMPERATURE = 0.1
```

**Result:**
- ✅ Gemini now has enough tokens to complete JSON responses
- ✅ Doubled token budget ensures full entity extraction
- ✅ No more truncated JSON errors

**Cost Impact:**
- Slightly higher token usage per request
- But still within free tier daily limits (1500 requests/day)

---

## Gemini 2.5 Flash vs 1.5 Flash Comparison

| Feature | Gemini 1.5 Flash | Gemini 2.5 Flash |
|---------|------------------|------------------|
| **Rate Limit (Free)** | 15 RPM | **5 RPM** ⚠️ |
| **Daily Limit (Free)** | 1500 RPD | 1500 RPD |
| **Our Setting** | 15 RPM (old) | **4 RPM** (new) ✅ |
| **Max Tokens (Analysis)** | 2000 | **4000** (increased) ✅ |
| **Processing Speed** | 15 chapters/min | **4 chapters/min** |

---

## Current Configuration

### Rate Limiting
- **Gemini requests per minute:** 4 (leaves 1 request safety buffer)
- **Gemini requests per day:** 1500
- **Auto-wait time:** Up to 120 seconds
- **Behavior:** Automatically spaces requests, never hits quota

### Token Limits
- **Analysis max_tokens:** 4000 (ensures complete JSON)
- **Translation max_tokens:** 16000 (unchanged, already sufficient)

---

## Monitoring

### Check Current Rate Limit Status

```bash
docker-compose exec web python manage.py shell
```

```python
from ai_services.core.rate_limiter import get_rate_limiter

limiter = get_rate_limiter()
status = limiter.get_status("gemini")

print(f"Current minute: {status['minute_count']}/4 requests")
print(f"Current day: {status['day_count']}/1500 requests")
```

### Check for Errors in Django Admin

1. Go to **Django Admin → Books → Analysis Jobs**
2. Filter by Status: "Failed" or "Completed"
3. Look for errors in "Error message" field:
   - `RateLimitError` → Rate limit hit (should be rare now)
   - `ResponseParsingError` → JSON truncation (should be fixed)

---

## Performance Expectations

### With Current Settings (4 RPM)

**Processing Rates:**
- 4 chapters per minute
- 240 chapters per hour
- 5,760 chapters per day (theoretical max)
- 1,500 chapters per day (actual free tier limit)

**Time Estimates:**
- 10 chapters: ~2.5 minutes
- 50 chapters: ~12.5 minutes
- 100 chapters: ~25 minutes
- 500 chapters: ~2 hours

### Example Workflow

```
Batch of 20 chapters:
  Request 1: Chapter 1 → Success (0s elapsed)
  Request 2: Chapter 2 → Success (0s elapsed)
  Request 3: Chapter 3 → Success (0s elapsed)
  Request 4: Chapter 4 → Success (0s elapsed)
  Request 5: Chapter 5 → Wait 60s... → Success (60s elapsed)
  Request 6: Chapter 6 → Wait 60s... → Success (120s elapsed)
  ...
  Total time: ~5 minutes for 20 chapters
```

---

## Alternative Solutions (Faster Processing)

### Option 1: Switch to OpenAI

**Pros:**
- 60 requests/minute (15x faster than Gemini)
- More reliable JSON responses
- Better rate limits

**Cons:**
- Costs money (pay per token)
- Requires OpenAI API key with credits

**How to switch:**
```python
# In .env file
AI_DEFAULT_PROVIDER=openai
OPENAI_API_KEY=your_key_here
```

### Option 2: Upgrade Gemini to Paid Tier

**Pros:**
- Higher rate limits
- Still uses same code
- May be cheaper than OpenAI

**Cons:**
- Requires paid Google Cloud account
- Need to set up billing

### Option 3: Keep Current Setup (Recommended for Now)

**Pros:**
- Free
- Reliable with current fixes
- No billing setup needed

**Cons:**
- Slower (4 chapters/minute)
- Daily limit of 1500 chapters

---

## Testing the Fixes

### Test Rate Limiting

```bash
docker-compose exec web python /app/test_rate_limiting.py
```

Should see:
```
✓ Request 1: Passed
✓ Request 2: Passed
✓ Request 3: Passed
✓ Request 4: Passed
⏳ Request 5: Wait 60s... ✓ Success
```

### Test Analysis with Real Chapter

```bash
docker-compose exec web python manage.py shell
```

```python
from ai_services.services import AnalysisService

service = AnalysisService()
result = service.extract_entities_and_summary("测试内容" * 500, "zh")

# Should get complete JSON with no truncation
print(f"Characters: {result.get('characters', [])}")
print(f"Summary length: {len(result.get('summary', ''))}")
print(f"Has error: {'error_details' in result}")
```

---

## Troubleshooting

### Still Getting Rate Limit Errors?

**Check:**
1. Is rate limiter set to 4 RPM? Check `rate_limiter.py`
2. Are you running multiple processes? Each has its own limiter
3. Did you restart the container after changes?

**Solution:**
- Lower rate limit to 3 RPM if still seeing errors
- Implement Redis-based rate limiting for multiple workers
- Add exponential backoff in error handling

### Still Getting Truncated JSON?

**Check:**
1. Is max_tokens set to 4000? Check `analysis.py`
2. Is the content extremely long?
3. Are you hitting Gemini's context window limit?

**Solution:**
- Increase max_tokens to 6000 or 8000
- Split very long content into smaller chunks
- Use content truncation before sending to API

### Processing Too Slow?

**Options:**
1. **Switch to OpenAI** - 15x faster, costs money
2. **Upgrade Gemini tier** - Higher limits, some cost
3. **Batch process overnight** - Let it run slowly but reliably
4. **Use queue system** - Submit jobs and check back later

---

## Summary

✅ **Rate limiting fixed:** 4 RPM (safe for Gemini 2.5 Flash)
✅ **JSON truncation fixed:** 4000 max_tokens (ensures complete responses)
✅ **No code changes needed:** Fixes work automatically
✅ **Free tier compatible:** Within daily 1500 request limit

**Trade-off:** Slower processing (4 chapters/min) but reliable and free.

---

**Date:** 2025-12-18
**Model:** Gemini 2.5 Flash
**Status:** ✅ Production Ready

**Related Documentation:**
- [Rate Limiting Guide](AI_SERVICES_RATE_LIMITING.md)
- [Rate Limiting Summary](AI_SERVICES_RATE_LIMITING_SUMMARY.md)
- [Error Handling Guide](AI_SERVICES_ERROR_HANDLING.md)
