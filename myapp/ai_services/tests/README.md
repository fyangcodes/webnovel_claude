# AI Services Test Suite

Comprehensive unit and integration tests for the modular AI services package.

## Test Structure

```
ai_services/tests/
├── __init__.py                 # Test package initialization
├── test_providers.py           # Provider tests (OpenAI, Gemini)
├── test_services.py            # Service tests (Analysis, Translation)
├── test_config.py              # Configuration tests
├── test_integration.py         # Integration tests with Django models
└── README.md                   # This file
```

## Test Categories

### 1. Provider Tests (`test_providers.py`)

Tests for OpenAI and Gemini provider implementations with mocked API responses.

**Coverage:**
- Provider initialization
- Chat completion success cases
- JSON response format handling
- Rate limit error handling
- API error handling
- Cross-provider compatibility
- Response format consistency

**Test Classes:**
- `TestOpenAIProvider` - OpenAI provider tests
- `TestGeminiProvider` - Gemini provider tests
- `TestProviderComparison` - Cross-provider compatibility

**Run:**
```bash
python manage.py test ai_services.tests.test_providers
```

### 2. Service Tests (`test_services.py`)

Tests for AnalysisService and TranslationService with mocked providers.

**Coverage:**
- Service initialization and provider selection
- Entity extraction and validation
- Translation workflow
- Error handling and retry logic
- Entity name cleaning
- Context gathering
- Provider switching

**Test Classes:**
- `TestAnalysisService` - Analysis service tests
- `TestTranslationServiceUnit` - Translation service tests
- `TestServiceProviderSwitching` - Provider selection tests

**Run:**
```bash
python manage.py test ai_services.tests.test_services
```

### 3. Configuration Tests (`test_config.py`)

Tests for configuration management and provider selection.

**Coverage:**
- Default provider configuration
- Service-specific provider overrides
- Configuration hierarchy (service > provider > default)
- API key validation
- Model selection
- Max tokens and temperature settings
- Environment variable fallbacks
- Mixed provider configurations

**Test Classes:**
- `TestAIServicesConfig` - Configuration management
- `TestConfigurationEdgeCases` - Edge cases and fallbacks
- `TestProviderSelection` - Provider selection logic

**Run:**
```bash
python manage.py test ai_services.tests.test_config
```

### 4. Integration Tests (`test_integration.py`)

End-to-end tests with real Django models and mocked API responses.

**Coverage:**
- ChapterContext creation and population
- BookEntity creation from analysis
- Chapter translation with entity consistency
- Entity translation storage and retrieval
- Multi-chapter context gathering
- Cross-provider consistency

**Test Classes:**
- `TestAnalysisServiceIntegration` - Analysis with Django models
- `TestTranslationServiceIntegration` - Translation with Django models
- `TestCrossProviderCompatibility` - Provider-agnostic functionality

**Run:**
```bash
python manage.py test ai_services.tests.test_integration
```

## Running Tests

### Run All AI Services Tests

```bash
# From project root
cd myapp
python manage.py test ai_services.tests

# With verbose output
python manage.py test ai_services.tests -v 2

# With coverage
coverage run --source='ai_services' manage.py test ai_services.tests
coverage report
coverage html  # Generate HTML report
```

### Run Specific Test File

```bash
python manage.py test ai_services.tests.test_providers
```

### Run Specific Test Class

```bash
python manage.py test ai_services.tests.test_providers.TestOpenAIProvider
```

### Run Specific Test Method

```bash
python manage.py test ai_services.tests.test_providers.TestOpenAIProvider.test_chat_completion_success
```

### Run in Docker

```bash
# Run all tests
docker-compose exec web python myapp/manage.py test ai_services.tests

# Run with coverage
docker-compose exec web coverage run --source='myapp/ai_services' myapp/manage.py test ai_services.tests
docker-compose exec web coverage report
```

## Test Coverage Goals

| Component | Coverage Target | Current Status |
|-----------|----------------|----------------|
| Providers | >90% | 🎯 Target |
| Services | >85% | 🎯 Target |
| Configuration | >90% | 🎯 Target |
| Integration | >80% | 🎯 Target |
| **Overall** | **>85%** | 🎯 **Target** |

## Mocking Strategy

### Provider Mocking

Provider tests use mocked API clients to avoid real API calls:

```python
@patch('ai_services.providers.openai_provider.OpenAI')
def test_chat_completion_success(self, mock_openai_class):
    # Mock OpenAI response
    mock_response = Mock()
    mock_response.choices[0].message.content = '{"result": "test"}'
    mock_client.chat.completions.create.return_value = mock_response

    # Test provider
    provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")
    response = provider.chat_completion(messages)
```

### Service Mocking

Service tests use `MockProvider` class to simulate provider responses:

```python
class MockProvider:
    def __init__(self, response_content, **kwargs):
        self.response_content = response_content

    def chat_completion(self, messages, **kwargs):
        return ChatCompletionResponse(
            content=self.response_content,
            model="mock",
            provider="mock",
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 50}
        )

# Usage
mock_provider = MockProvider('{"characters": ["Test"]}')
service = AnalysisService()
service.provider = mock_provider
result = service.extract_entities_and_summary("content", "zh")
```

### Django Model Mocking

Integration tests use real Django models with test database:

```python
class TestTranslationServiceIntegration(TestCase):
    def setUp(self):
        # Create test data in test database
        self.user = User.objects.create_user(username="test")
        self.language = Language.objects.create(code="zh", name="Chinese")
        self.book = Book.objects.create(...)
```

## Test Data

### Sample Responses

**Analysis Response:**
```json
{
    "characters": ["李明", "张伟"],
    "places": ["北京", "上海"],
    "terms": ["修炼", "功法"],
    "summary": "李明和张伟分别在不同城市修炼。"
}
```

**Translation Response:**
```json
{
    "title": "Chapter 1: Beginning",
    "content": "Li Ming cultivates techniques in Beijing...",
    "entity_mappings": {
        "李明": "Li Ming",
        "北京": "Beijing",
        "功法": "techniques"
    }
}
```

## Common Test Patterns

### Testing Provider Initialization

```python
def test_initialization(self):
    provider = OpenAIProvider(api_key="test-key", model="gpt-4o-mini")
    self.assertEqual(provider.model, "gpt-4o-mini")
    self.assertIsNotNone(provider.client)
```

### Testing Error Handling

```python
def test_rate_limit_error(self, mock_openai_class):
    mock_client.chat.completions.create.side_effect = RateLimitError("Rate limit")

    provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")
    with self.assertRaises(RateLimitError):
        provider.chat_completion(messages)
```

### Testing Service Retry Logic

```python
def test_extract_entities_with_retry(self):
    call_count = [0]

    def mock_completion(messages, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise APIError("Temporary error")
        return ChatCompletionResponse(...)

    service.max_retries = 2
    result = service.extract_entities_and_summary("content", "zh")
    self.assertEqual(call_count[0], 2)  # Verify retry worked
```

### Testing Django Integration

```python
def test_translation_creates_chapter(self):
    mock_provider = self._create_mock_provider(mock_response)
    service = TranslationService()
    service.provider = mock_provider

    translated_chapter = service.translate_chapter(source_chapter, "en")

    self.assertIsNotNone(translated_chapter)
    self.assertEqual(translated_chapter.book.language.code, "en")
```

## Continuous Integration

### GitHub Actions

Add to `.github/workflows/tests.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.12

      - name: Install dependencies
        run: |
          pip install -r requirements/development.txt

      - name: Run tests
        run: |
          cd myapp
          python manage.py test ai_services.tests
        env:
          DJANGO_SETTINGS_MODULE: myapp.settings
          OPENAI_API_KEY: test-key
          GEMINI_API_KEY: test-key

      - name: Generate coverage report
        run: |
          coverage run --source='ai_services' manage.py test ai_services.tests
          coverage report
          coverage xml

      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          file: ./coverage.xml
```

## Troubleshooting

### Import Errors

If you get `ModuleNotFoundError`:

```bash
# Ensure PYTHONPATH includes myapp directory
export PYTHONPATH=/path/to/webnovel_claude/myapp:$PYTHONPATH

# Or run from myapp directory
cd myapp
python manage.py test ai_services.tests
```

### Django Settings Not Configured

```bash
# Set Django settings module
export DJANGO_SETTINGS_MODULE=myapp.settings

# Or specify in command
python manage.py test ai_services.tests --settings=myapp.settings
```

### Database Errors

```bash
# Run migrations first
python manage.py migrate

# Or use test database
python manage.py test --keepdb ai_services.tests
```

### Mock Import Errors

Ensure you have the correct imports:

```python
from unittest.mock import Mock, patch, MagicMock  # Python 3
```

## Best Practices

1. **Always mock external APIs** - Never make real API calls in tests
2. **Use descriptive test names** - `test_chat_completion_success` not `test_1`
3. **Test one thing per test** - Each test should verify a single behavior
4. **Use setUp for common data** - Avoid repetition in test methods
5. **Test error paths** - Don't just test happy paths
6. **Verify all assertions** - Check return values, side effects, and state changes
7. **Keep tests fast** - Use mocks, avoid real I/O
8. **Make tests independent** - Tests should not depend on each other
9. **Clean up after tests** - Django TestCase handles this automatically
10. **Document complex tests** - Add comments explaining non-obvious logic

## Future Improvements

- [ ] Add performance benchmarking tests
- [ ] Add load testing for concurrent requests
- [ ] Add contract tests for provider interfaces
- [ ] Add mutation testing
- [ ] Add property-based testing with Hypothesis
- [ ] Add visual regression tests for rendered content
- [ ] Add end-to-end tests with real API calls (optional, separate suite)

## Resources

- [Django Testing Documentation](https://docs.djangoproject.com/en/5.0/topics/testing/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)

---

**Last Updated:** 2025-12-18
**Test Suite Version:** 1.0.0
**Total Tests:** 50+
**Estimated Runtime:** < 5 seconds
