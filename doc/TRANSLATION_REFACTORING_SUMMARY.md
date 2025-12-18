# Translation Refactoring Summary

**Quick Reference Guide for [TRANSLATION_REFACTORING_PLAN.md](TRANSLATION_REFACTORING_PLAN.md)**

---

## What This Refactoring Does

Transforms the current OpenAI-only translation system into a **modular, multi-provider AI services package** that supports both OpenAI and Google Gemini (and future providers).

---

## Current Problems

1. **Hardcoded OpenAI dependency** - Can't use alternative providers
2. **No abstraction layer** - Business logic mixed with API calls
3. **Difficult to test** - Can't mock AI providers easily
4. **Inflexible configuration** - Can't switch providers without code changes
5. **No cost optimization** - Stuck with single provider's pricing

---

## New Architecture Overview

```
ai_services/                          # New modular package
├── core/                             # Core abstractions
│   ├── base.py                       # BaseAIProvider interface
│   ├── models.py                     # ChatMessage, Response models
│   ├── exceptions.py                 # Unified exceptions
│   └── registry.py                   # Provider registry
├── providers/                        # Provider implementations
│   ├── openai_provider.py            # OpenAI adapter
│   └── gemini_provider.py            # Gemini adapter
├── services/                         # Business logic (provider-agnostic)
│   ├── analysis.py                   # Entity extraction service
│   └── translation.py                # Translation service
└── prompts/                          # Prompt templates
    ├── analysis.py                   # Analysis prompts
    └── translation.py                # Translation prompts
```

---

## Key Design Decisions

### 1. **Provider Abstraction**
All providers implement `BaseAIProvider` interface:
```python
class BaseAIProvider(ABC):
    def chat_completion(self, messages, max_tokens, temperature, response_format):
        """Unified method for all providers"""
        pass
```

### 2. **Unified Data Models**
```python
@dataclass
class ChatMessage:
    role: str  # "system", "user", "assistant"
    content: str

@dataclass
class ChatCompletionResponse:
    content: str
    model: str
    provider: str  # "openai" or "gemini"
    usage: Dict[str, int]
```

### 3. **Provider Registry**
Dynamic provider registration:
```python
ProviderRegistry.register('openai', OpenAIProvider)
ProviderRegistry.register('gemini', GeminiProvider)

provider = ProviderRegistry.get('openai')
```

### 4. **Service Layer Separation**
Services are provider-agnostic:
```python
# Works with any provider
service = TranslationService(provider_name='gemini')
service = TranslationService(provider_name='openai')
```

---

## Migration Strategy

### Backward Compatibility
Old code keeps working via compatibility wrappers:

```python
# Old way (still works)
from books.utils import ChapterTranslationService
service = ChapterTranslationService()

# New way (recommended)
from ai_services.services import TranslationService
service = TranslationService(provider_name='gemini')
```

### Migration Timeline
- **Weeks 1-4:** Build new package (no breaking changes)
- **Week 5:** Django integration + compatibility layer
- **Week 6:** Documentation
- **Weeks 7-8:** Gradual migration of existing code
- **Week 9:** Remove compatibility wrappers (major version bump)

---

## Configuration

### New Settings
```python
# settings.py

# Global default
AI_DEFAULT_PROVIDER = 'openai'  # or 'gemini'

# OpenAI config
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_TRANSLATION_MODEL = 'gpt-4o-mini'
OPENAI_ANALYSIS_MODEL = 'gpt-4o-mini'

# Gemini config
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_TRANSLATION_MODEL = 'gemini-2.0-flash-exp'
GEMINI_ANALYSIS_MODEL = 'gemini-2.0-flash-exp'

# Per-service overrides
TRANSLATION_PROVIDER = 'openai'
ANALYSIS_PROVIDER = 'gemini'  # Use cheaper Gemini for analysis
```

### Environment Variables
```bash
# .env
AI_DEFAULT_PROVIDER=openai
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AI...

# Mix and match
TRANSLATION_PROVIDER=openai  # High quality
ANALYSIS_PROVIDER=gemini     # Lower cost
```

---

## Usage Examples

### Current Usage (Unchanged)
```python
from books.utils import ChapterTranslationService

service = ChapterTranslationService()
translated = service.translate_chapter(chapter, 'en')
```

### New Usage (Provider-Agnostic)
```python
from ai_services.services import TranslationService

# Use OpenAI
service = TranslationService(provider_name='openai')
translated = service.translate_chapter(chapter, 'en')

# Switch to Gemini (no code changes needed)
service = TranslationService(provider_name='gemini')
translated = service.translate_chapter(chapter, 'en')
```

### Configuration-Based (Recommended)
```python
# Uses provider from settings
service = TranslationService()  # Uses AI_DEFAULT_PROVIDER
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- Create package structure
- Implement abstractions
- Provider registry
- Exception hierarchy

**Deliverable:** Foundation ready, no breaking changes

### Phase 2: OpenAI Provider (Week 2)
- Port OpenAI logic to new provider
- Verify behavior matches current implementation
- Comprehensive tests

**Deliverable:** OpenAI provider working

### Phase 3: Gemini Provider (Week 3)
- Implement Gemini provider
- Handle Gemini-specific API differences
- Cross-provider tests

**Deliverable:** Can switch between providers

### Phase 4: Service Layer (Week 4)
- Provider-agnostic services
- Separate prompt templates
- Business logic refactoring

**Deliverable:** Services work with any provider

### Phase 5: Integration (Week 5)
- Django integration
- Compatibility wrappers
- Update tasks and commands

**Deliverable:** Production-ready

### Phase 6: Documentation (Week 6)
- Architecture docs
- Migration guide
- Usage examples

**Deliverable:** Ready for team adoption

---

## Benefits

### 1. **Flexibility**
- Switch providers without code changes
- Use different providers for different tasks
- Easy to add new providers (Anthropic, Cohere, local models)

### 2. **Cost Optimization**
```python
# Use cheaper Gemini for analysis
ANALYSIS_PROVIDER = 'gemini'  # $0.15 per million tokens

# Use better OpenAI for translation
TRANSLATION_PROVIDER = 'openai'  # $0.60 per million tokens
```

### 3. **Testing**
```python
# Mock providers in tests
class MockProvider(BaseAIProvider):
    def chat_completion(self, messages, **kwargs):
        return ChatCompletionResponse(content="mocked", ...)

# No API calls in unit tests
```

### 4. **Reliability**
- Automatic fallback if primary provider fails
- Provider health checking
- Better error handling

### 5. **Maintainability**
- Clear separation of concerns
- Provider logic isolated
- Easier to debug and extend

---

## Testing Strategy

### Unit Tests
```python
# Test providers independently
def test_openai_provider():
    provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")
    response = provider.chat_completion([ChatMessage(...)])
    assert response.provider == "openai"

# Test services with mocked providers
def test_translation_service(mock_provider):
    service = TranslationService(provider=mock_provider)
    result = service.translate(...)
    assert result
```

### Integration Tests
```python
# Test with both providers
@pytest.mark.parametrize('provider', ['openai', 'gemini'])
def test_full_translation_workflow(provider):
    service = TranslationService(provider_name=provider)
    translated = service.translate_chapter(chapter, 'en')
    assert translated.content
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking changes | Backward compatibility wrappers |
| Provider API differences | Unified response format, adapters |
| Performance issues | Benchmarking, profiling, optimization |
| Configuration complexity | Sensible defaults, validation |

---

## Success Criteria

**Must Have:**
- [ ] All existing functionality works
- [ ] Can switch providers via config
- [ ] No breaking changes
- [ ] >85% test coverage
- [ ] Documentation complete

**Nice to Have:**
- [ ] Performance equal or better
- [ ] Cost savings via mixed providers
- [ ] Production deployment successful

---

## Next Steps

1. **Review this plan** - Get team feedback
2. **Set up development environment** - Install Gemini SDK
3. **Start Phase 1** - Build core infrastructure
4. **Weekly checkpoints** - Review progress each week
5. **Testing throughout** - Don't skip tests

---

## Quick Reference

**Full Plan:** [TRANSLATION_REFACTORING_PLAN.md](TRANSLATION_REFACTORING_PLAN.md)

**Key Files:**
- `ai_services/core/base.py` - Provider interface
- `ai_services/providers/openai_provider.py` - OpenAI implementation
- `ai_services/providers/gemini_provider.py` - Gemini implementation
- `ai_services/services/translation.py` - Translation service
- `ai_services/services/analysis.py` - Analysis service

**Configuration:**
- Settings: `myapp/settings.py`
- Environment: `.env`

**Testing:**
- Unit: `tests/ai_services/test_providers.py`
- Integration: `tests/ai_services/integration/test_workflows.py`

---

## Questions?

Refer to the full plan for:
- Detailed code examples
- API documentation
- Error handling strategies
- Performance considerations
- Future enhancements
