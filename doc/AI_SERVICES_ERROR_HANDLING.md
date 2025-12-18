# Enhanced Error Handling in AI Services

**Date:** 2025-12-18
**Status:** ✅ **IMPLEMENTED**

---

## Overview

The AI services now include comprehensive error handling that captures detailed debugging information when analysis or translation fails. This includes the full prompt sent, the response received, and relevant context data.

---

## What Was Implemented

### 1. Analysis Service Error Handling

**File:** [myapp/ai_services/services/analysis.py](../myapp/ai_services/services/analysis.py)

**Enhancements:**
- ✅ Captures validation errors (invalid JSON, missing fields)
- ✅ Records full prompt sent to AI provider
- ✅ Records full response received (truncated to 2000 chars)
- ✅ Includes content preview (first 500 chars)
- ✅ Includes provider and model information
- ✅ Returns fallback result with error_details field

**Error Details Format:**
```
=== Analysis Error Details ===
Error Type: ResponseParsingError
Error Message: Invalid JSON response: Expecting value: line 1 column 1 (char 0)
Provider: openai
Model: gpt-4o-mini

--- Content Preview (first 500 chars) ---
李明在北京修炼，他的朋友张伟来自上海...

--- Prompt Sent ---
You are analyzing a Chinese webnovel chapter to extract entities...
[Full prompt up to 2000 chars]
... (prompt truncated, total length: 3500 chars)

--- Response Received ---
This is not valid JSON!
(No response received)

=== End Error Details ===
```

### 2. Translation Service Error Handling

**File:** [myapp/ai_services/services/translation.py](../myapp/ai_services/services/translation.py)

**Enhancements:**
- ✅ Captures validation errors (missing required fields)
- ✅ **Validates entity mappings** - checks if expected entities were translated
- ✅ Records full prompt including translation context
- ✅ Records full response (truncated to 3000 chars)
- ✅ Includes content preview and chapter title
- ✅ Shows expected vs received entity mappings
- ✅ Provides translation context (found entities, new entities, previous chapters)

**Error Details Format:**
```
=== Translation Error Details ===
Error Type: MissingEntityMappingsError
Error Message: Translation did not include mappings for 3 expected entities: 李明, 功法, 张真人
Provider: openai
Model: gpt-4o-mini
Title: 第一章

--- Content Preview (first 500 chars) ---
李明在北京修炼功法，他的师父是张真人...

--- Translation Context ---
Found entities (with translations): 2
  北京, 修炼
New entities (need translation): 4
  李明, 功法, 张真人, 阵法
Previous chapters for context: 2
Expected entities: 4
Received mappings: 1
Missing: 3

--- Prompt Sent ---
Translate the following webnovel chapter from Chinese to English...
[Full prompt up to 3000 chars]

--- Response Received ---
{"title": "Chapter 1", "content": "...", "entity_mappings": {"北京": "Beijing"}}
... (response truncated, total length: 5000 chars)

=== End Error Details ===
```

### 3. Celery Task Integration

**File:** [myapp/books/tasks/chapter_analysis.py](../myapp/books/tasks/chapter_analysis.py)

**Changes:**
- ✅ Checks for `error_details` field in analysis result
- ✅ Stores error details in job's `error_message` field
- ✅ Marks job as completed (with warnings) if validation failed but fallback result returned
- ✅ Logs warning when validation errors occur

**File:** [myapp/books/tasks/chapter_translation.py](../myapp/books/tasks/chapter_translation.py)

**Changes:**
- ✅ No changes needed - existing error handling already captures full exception message
- ✅ Enhanced exceptions now include error details automatically
- ✅ ValidationError and APIError exceptions include formatted error details

---

## How It Works

### Analysis Service Error Flow

```python
# User code (unchanged)
from books.utils import ChapterAnalysisService

service = ChapterAnalysisService()
result = service.extract_entities_and_summary(content, "zh")

# What happens internally:
# 1. Build prompt from content
# 2. Call AI provider (OpenAI or Gemini)
# 3. Receive response
# 4. Try to parse JSON
#    ├─ Success: validate required fields
#    │   ├─ Valid: return result
#    │   └─ Invalid: capture error details, return fallback + error_details
#    └─ Failure: capture error details, return fallback + error_details

# Result structure:
{
    "characters": [],  # May be empty if error
    "places": [],
    "terms": [],
    "summary": "FALLBACK: content preview...",  # Fallback summary
    "error_details": "=== Analysis Error Details ===\n..."  # Full error info (if error)
}
```

### Translation Service Error Flow

```python
# User code (unchanged)
from books.utils import ChapterTranslationService

service = ChapterTranslationService()
translated_chapter = service.translate_chapter(source_chapter, "en")

# What happens internally:
# 1. Gather translation context (entities, previous chapters)
# 2. Build prompt with context
# 3. Call AI provider
# 4. Receive response
# 5. Try to parse JSON
#    ├─ Success: validate required fields
#    │   ├─ Valid: check entity mappings
#    │   │   ├─ All present: return result
#    │   │   └─ Some missing: log warning, add warning to result
#    │   └─ Invalid: raise ValidationError with error details
#    └─ Failure: raise ResponseParsingError with error details

# If ValidationError or APIError raised:
# Exception message includes:
#   - Original error message
#   - "\n\nError Details:\n"
#   - Full formatted error details (prompt, response, context)
```

### Celery Task Integration

```python
# Analysis task (chapter_analysis.py)
result = context.analyze_chapter()  # Calls AnalysisService internally

if 'error_details' in result:
    job.status = ProcessingStatus.COMPLETED
    job.error_message = result['error_details']  # Store full error details
    logger.warning("Analysis completed with validation errors")
else:
    job.status = ProcessingStatus.COMPLETED
    job.error_message = ""

# Translation task (chapter_translation.py)
try:
    service.translate_chapter(job.chapter, job.target_language.code)
    job.status = ProcessingStatus.COMPLETED
    job.error_message = ""
except TranslationValidationError as e:
    job.status = ProcessingStatus.FAILED
    job.error_message = str(e)  # Now includes error details!
```

---

## Benefits

### 1. **Debugging AI Failures**

**Before:**
```
Error: Invalid JSON response
```
- No idea what the AI actually returned
- Can't reproduce the issue
- Can't improve prompts

**After:**
```
Error: Invalid JSON response

Error Details:
Provider: openai
Model: gpt-4o-mini
Prompt: "Extract entities from: 李明在北京..."
Response: "This is a narrative about Li Ming in Beijing, who..."
```
- See exactly what went wrong
- Can test with the exact same prompt
- Can improve prompt engineering

### 2. **Entity Mapping Validation**

**Before:**
- Translation succeeds even if entities not translated
- Inconsistent entity names across chapters
- No way to know which entities were missed

**After:**
- Validation checks if expected entities were translated
- Warning logged with missing entity names
- Error details show expected vs received mappings
- Can fix prompts to emphasize important entities

### 3. **Production Monitoring**

**Before:**
```sql
SELECT * FROM books_analysisjob WHERE status = 'FAILED';
-- Shows: "API Error"
```

**After:**
```sql
SELECT error_message FROM books_analysisjob WHERE status = 'COMPLETED' AND error_message != '';
-- Shows full error details including prompts and responses
```

Can now:
- Identify patterns in failures
- See if specific content triggers errors
- Detect provider-specific issues
- Improve prompts based on real failures

---

## Example Error Messages Stored in Database

### Analysis Job with Validation Error

```
=== Analysis Error Details ===
Error Type: ValidationError
Error Message: Missing required field: summary
Provider: openai
Model: gpt-4o-mini

--- Content Preview (first 500 chars) ---
第一千二百三十四章 突破

李明盘坐在洞府之中，周身灵气涌动...

--- Prompt Sent ---
You are analyzing a Chinese webnovel chapter...
Please extract the following information:
1. Characters (人物): Names of characters mentioned
2. Places (地点): Names of locations
3. Terms (术语): Special cultivation terms, techniques...
[... full prompt ...]

--- Response Received ---
{
  "characters": ["李明", "张真人"],
  "places": ["洞府"],
  "terms": ["突破", "灵气"]
}
(Missing 'summary' field)

=== End Error Details ===
```

### Translation Job with Missing Entity Mappings

```
=== Translation Error Details ===
Error Type: MissingEntityMappingsError
Error Message: Translation did not include mappings for 5 expected entities: 李明, 功法, 阵法, 灵气, 突破
Provider: gemini
Model: gemini-2.0-flash-exp
Title: 第一千二百三十四章 突破

--- Content Preview (first 500 chars) ---
李明盘坐在洞府之中，周身灵气涌动，他正在尝试突破筑基期...

--- Translation Context ---
Found entities (with translations): 3
  洞府 → Cave Abode
  筑基期 → Foundation Establishment
  金丹期 → Golden Core
New entities (need translation): 5
  李明, 功法, 阵法, 灵气, 突破
Previous chapters for context: 5
Expected entities: 5
Received mappings: 0
Missing: 5

--- Prompt Sent ---
Translate the following webnovel chapter from Chinese to English.

IMPORTANT: Maintain consistency with these previously translated entities:
- 洞府 → Cave Abode
- 筑基期 → Foundation Establishment
...

NEW ENTITIES (Please translate these and include in entity_mappings):
- 李明
- 功法
- 阵法
- 灵气
- 突破

[... full translation prompt ...]

--- Response Received ---
{
  "title": "Chapter 1234: Breakthrough",
  "content": "Li Ming sat cross-legged in his Cave Abode, spiritual energy swirling around him as he attempted to break through to Foundation Establishment...",
  "entity_mappings": {}
}
(Empty entity_mappings despite being asked to translate 5 entities)

=== End Error Details ===
```

---

## Configuration

### Error Detail Truncation

Error details are truncated to prevent database overflow:

- **Analysis Service:**
  - Prompts: 2000 characters max
  - Responses: 2000 characters max
  - Content preview: 500 characters

- **Translation Service:**
  - Prompts: 3000 characters max
  - Responses: 3000 characters max
  - Content preview: 500 characters

These limits can be adjusted in the service files if needed.

### Logging Levels

Error details are logged at appropriate levels:

- **Validation errors:** `logger.warning()` (expected, recoverable)
- **API errors:** `logger.error()` (unexpected, may need investigation)
- **Successful operations:** `logger.info()` (normal operation)

---

## Viewing Error Details

### Django Admin

1. Go to **Books > Analysis Jobs** or **Books > Translation Jobs**
2. Click on a job with errors
3. View the **Error message** field - now contains full error details
4. Search for specific error patterns using admin search

### Database Queries

```sql
-- Find analysis jobs with validation errors
SELECT
    id,
    chapter_id,
    created_at,
    error_message
FROM books_analysisjob
WHERE error_message LIKE '%=== Analysis Error Details ===%'
ORDER BY created_at DESC
LIMIT 10;

-- Find translation jobs with missing entity mappings
SELECT
    id,
    chapter_id,
    target_language_id,
    error_message
FROM books_translationjob
WHERE error_message LIKE '%MissingEntityMappingsError%'
ORDER BY created_at DESC;

-- Count errors by type
SELECT
    CASE
        WHEN error_message LIKE '%ValidationError%' THEN 'Validation Error'
        WHEN error_message LIKE '%ResponseParsingError%' THEN 'Parsing Error'
        WHEN error_message LIKE '%MissingEntityMappingsError%' THEN 'Missing Entities'
        WHEN error_message LIKE '%APIError%' THEN 'API Error'
        ELSE 'Other'
    END as error_type,
    COUNT(*) as count
FROM books_analysisjob
WHERE error_message != ''
GROUP BY error_type;
```

### Logs

Error details are also written to Django logs:

```bash
# View recent errors
tail -f logs/django.log | grep "Error Details"

# Search for specific errors
grep "Missing required field" logs/django.log

# Find all validation failures
grep "validation failed" logs/django.log
```

---

## Best Practices

### 1. Monitor Error Patterns

Regularly check for common error patterns:

```python
# Example monitoring script
from books.models import AnalysisJob, TranslationJob

# Check analysis errors
failed_analysis = AnalysisJob.objects.filter(
    error_message__contains="=== Analysis Error Details ==="
).count()

# Check translation entity mapping issues
missing_entities = TranslationJob.objects.filter(
    error_message__contains="MissingEntityMappingsError"
).count()

print(f"Analysis validation errors: {failed_analysis}")
print(f"Translation missing entities: {missing_entities}")
```

### 2. Use Error Details to Improve Prompts

When you see repeated validation errors:

1. Check the error details in the database
2. Review the prompt that was sent
3. Review the response that was received
4. Update the prompt template to be more explicit
5. Test with the same content

### 3. Set Up Alerts

Create alerts for high error rates:

```python
# Example: Send alert if error rate > 10%
from django.core.mail import send_mail

total_jobs = AnalysisJob.objects.count()
error_jobs = AnalysisJob.objects.exclude(error_message="").count()
error_rate = (error_jobs / total_jobs * 100) if total_jobs > 0 else 0

if error_rate > 10:
    send_mail(
        subject="High AI Service Error Rate",
        message=f"Error rate: {error_rate:.1f}%\nCheck error details in admin.",
        from_email="alerts@example.com",
        recipient_list=["admin@example.com"],
    )
```

---

## Future Enhancements

Potential improvements for the future:

- [ ] Add error detail summary dashboard
- [ ] Implement error pattern detection and grouping
- [ ] Add retry with adjusted prompts for validation errors
- [ ] Create error detail export for analysis
- [ ] Add AI provider comparison (which fails less)
- [ ] Implement automatic prompt improvement based on errors

---

## Files Modified

1. **[myapp/ai_services/services/analysis.py](../myapp/ai_services/services/analysis.py)**
   - Added `_format_error_details()` method
   - Enhanced error handling in `extract_entities_and_summary()`
   - Returns error_details field in result dict

2. **[myapp/ai_services/services/translation.py](../myapp/ai_services/services/translation.py)**
   - Added `_format_translation_error_details()` method
   - Added `_validate_entity_mappings()` method
   - Enhanced error handling in `_translate_with_context()`
   - Raises exceptions with embedded error details

3. **[myapp/books/tasks/chapter_analysis.py](../myapp/books/tasks/chapter_analysis.py)**
   - Checks for error_details in result
   - Stores error_details in job.error_message
   - Logs warnings for validation errors

4. **[test_error_handling.py](../test_error_handling.py)**
   - Demonstration script for error handling
   - Shows error details format for various scenarios

---

**Prepared by:** Claude Code
**Date:** 2025-12-18
**Status:** ✅ **FULLY IMPLEMENTED**
