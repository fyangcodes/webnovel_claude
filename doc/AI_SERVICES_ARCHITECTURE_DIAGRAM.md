# AI Services Architecture Diagram

**Visual reference for the modular AI services architecture**

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Django Application                          │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    Django Models & Tasks                      │ │
│  │                                                               │ │
│  │  ┌──────────────────┐         ┌──────────────────┐          │ │
│  │  │ TranslationJob   │         │  AnalysisJob     │          │ │
│  │  │ Chapter          │         │  ChapterContext  │          │ │
│  │  │ BookEntity       │         │  BookEntity      │          │ │
│  │  └────────┬─────────┘         └────────┬─────────┘          │ │
│  │           │                             │                     │ │
│  └───────────┼─────────────────────────────┼─────────────────────┘ │
│              │                             │                       │
│  ┌───────────▼─────────────────────────────▼─────────────────────┐ │
│  │              AI Services Package (New)                        │ │
│  │                                                               │ │
│  │  ┌─────────────────────────────────────────────────────────┐ │ │
│  │  │              Service Layer (Provider-Agnostic)          │ │ │
│  │  │                                                         │ │ │
│  │  │  ┌──────────────────────┐   ┌────────────────────────┐ │ │ │
│  │  │  │ TranslationService   │   │  AnalysisService       │ │ │ │
│  │  │  │                      │   │                        │ │ │ │
│  │  │  │ - translate_chapter()│   │ - extract_entities()   │ │ │ │
│  │  │  │ - gather_context()   │   │ - clean_entities()     │ │ │ │
│  │  │  │ - parse_result()     │   │ - validate_result()    │ │ │ │
│  │  │  └──────────┬───────────┘   └───────────┬────────────┘ │ │ │
│  │  │             │                           │              │ │ │
│  │  └─────────────┼───────────────────────────┼──────────────┘ │ │
│  │                │                           │                │ │
│  │  ┌─────────────▼───────────────────────────▼──────────────┐ │ │
│  │  │              Prompt Templates                          │ │ │
│  │  │                                                        │ │ │
│  │  │  ┌──────────────────────┐   ┌──────────────────────┐ │ │ │
│  │  │  │ TranslationPrompt    │   │  AnalysisPrompt      │ │ │ │
│  │  │  │  Builder             │   │   Builder            │ │ │ │
│  │  │  └──────────────────────┘   └──────────────────────┘ │ │ │
│  │  └────────────────────────────────────────────────────────┘ │ │
│  │                                                               │ │
│  │  ┌─────────────────────────────────────────────────────────┐ │ │
│  │  │              Provider Registry & Selection              │ │ │
│  │  │                                                         │ │ │
│  │  │         ProviderRegistry.get(provider_name)            │ │ │
│  │  │                        │                               │ │ │
│  │  └────────────────────────┼───────────────────────────────┘ │ │
│  │                           │                                 │ │
│  │  ┌────────────────────────▼───────────────────────────────┐ │ │
│  │  │              Provider Abstraction Layer                │ │ │
│  │  │                                                         │ │ │
│  │  │                BaseAIProvider (ABC)                    │ │ │
│  │  │                                                         │ │ │
│  │  │  • chat_completion(messages, max_tokens, ...)          │ │ │
│  │  │  • validate_settings()                                 │ │ │
│  │  │  • get_model_info()                                    │ │ │
│  │  │                                                         │ │ │
│  │  └─────────────────┬───────────────────┬───────────────────┘ │ │
│  │                    │                   │                     │ │
│  └────────────────────┼───────────────────┼─────────────────────┘ │
│                       │                   │                       │
└───────────────────────┼───────────────────┼───────────────────────┘
                        │                   │
         ┌──────────────▼──────────┐   ┌────▼───────────────────┐
         │  OpenAI Provider        │   │  Gemini Provider       │
         │                         │   │                        │
         │  - OpenAI SDK           │   │  - Gemini SDK          │
         │  - API adapter          │   │  - API adapter         │
         │  - Response mapping     │   │  - Response mapping    │
         └──────────────┬──────────┘   └────┬───────────────────┘
                        │                   │
         ┌──────────────▼──────────┐   ┌────▼───────────────────┐
         │   OpenAI API            │   │   Gemini API           │
         │   (api.openai.com)      │   │   (ai.google.dev)      │
         └─────────────────────────┘   └────────────────────────┘
```

---

## Request Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Translation Request Flow                         │
└─────────────────────────────────────────────────────────────────────┘

1. Celery Task
   │
   ▼
2. TranslationService.translate_chapter(chapter, 'en')
   │
   ├─► Gather context from Django models
   │   ├─► Previous chapters
   │   ├─► Entity translations
   │   └─► Chapter summaries
   │
   ├─► Build prompt using TranslationPromptBuilder
   │   └─► Generate structured prompt with context
   │
   ├─► Select provider from registry
   │   ├─► Check configuration (settings.TRANSLATION_PROVIDER)
   │   └─► Get provider instance (OpenAI or Gemini)
   │
   ├─► Call provider.chat_completion()
   │   │
   │   ├─► OpenAI Path:
   │   │   ├─► Convert to OpenAI message format
   │   │   ├─► Call OpenAI API
   │   │   └─► Convert response to unified format
   │   │
   │   └─► Gemini Path:
   │       ├─► Convert to Gemini message format
   │       ├─► Call Gemini API
   │       └─► Convert response to unified format
   │
   ├─► Parse JSON response
   │   ├─► Extract: title, content, entity_mappings, notes
   │   └─► Validate structure
   │
   └─► Create Django models
       ├─► Create/update Chapter
       ├─► Store entity mappings to BookEntity
       └─► Update book metadata
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Unified Data Models                              │
└─────────────────────────────────────────────────────────────────────┘

Input (Service → Provider):
┌──────────────────────────────────────┐
│         ChatMessage[]                │
│                                      │
│  ┌────────────────────────────────┐ │
│  │ role: "user"                   │ │
│  │ content: "Translate chapter..."│ │
│  └────────────────────────────────┘ │
└──────────────────────────────────────┘
              │
              ▼
    ┌─────────────────────┐
    │   BaseAIProvider    │
    │  .chat_completion() │
    └─────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│    ChatCompletionResponse            │
│                                      │
│  content: "Translated text..."       │
│  model: "gpt-4o-mini"                │
│  provider: "openai"                  │
│  finish_reason: "stop"               │
│  usage: {                            │
│    prompt_tokens: 1500,              │
│    completion_tokens: 3000           │
│  }                                   │
└──────────────────────────────────────┘
```

---

## Provider Implementations

```
┌─────────────────────────────────────────────────────────────────────┐
│                     OpenAI Provider Flow                            │
└─────────────────────────────────────────────────────────────────────┘

ChatMessage[] (Unified)
      │
      ▼
┌─────────────────────────┐
│ Convert to OpenAI Format│
│                         │
│ [                       │
│   {                     │
│     "role": "user",     │
│     "content": "..."    │
│   }                     │
│ ]                       │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  OpenAI SDK             │
│  client.chat            │
│   .completions          │
│   .create()             │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  OpenAI Response        │
│                         │
│  response.choices[0]    │
│   .message.content      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Convert to Unified      │
│                         │
│ ChatCompletionResponse  │
│  (provider="openai")    │
└─────────────────────────┘


┌─────────────────────────────────────────────────────────────────────┐
│                     Gemini Provider Flow                            │
└─────────────────────────────────────────────────────────────────────┘

ChatMessage[] (Unified)
      │
      ▼
┌─────────────────────────┐
│ Convert to Gemini Format│
│                         │
│ system_instruction = "" │
│ history = [             │
│   {                     │
│     "role": "user",     │
│     "parts": ["..."]    │
│   }                     │
│ ]                       │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Gemini SDK             │
│  model.generate_content │
│   or chat.send_message  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Gemini Response        │
│                         │
│  response.text          │
│  response.usage_metadata│
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Convert to Unified      │
│                         │
│ ChatCompletionResponse  │
│  (provider="gemini")    │
└─────────────────────────┘
```

---

## Configuration Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Configuration Hierarchy                         │
└─────────────────────────────────────────────────────────────────────┘

1. Environment Variables (.env)
   │
   │  AI_DEFAULT_PROVIDER=openai
   │  OPENAI_API_KEY=sk-...
   │  GEMINI_API_KEY=AI...
   │  TRANSLATION_PROVIDER=openai
   │  ANALYSIS_PROVIDER=gemini
   │
   ▼
2. Django Settings (settings.py)
   │
   │  AI_DEFAULT_PROVIDER = os.getenv('AI_DEFAULT_PROVIDER', 'openai')
   │  OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
   │  GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
   │  TRANSLATION_PROVIDER = os.getenv('TRANSLATION_PROVIDER', AI_DEFAULT_PROVIDER)
   │  ANALYSIS_PROVIDER = os.getenv('ANALYSIS_PROVIDER', AI_DEFAULT_PROVIDER)
   │
   ▼
3. Service Initialization
   │
   │  # Uses TRANSLATION_PROVIDER from settings
   │  service = TranslationService()
   │
   │  # OR explicit override
   │  service = TranslationService(provider_name='gemini')
   │
   ▼
4. Provider Selection
   │
   │  provider_class = ProviderRegistry.get('gemini')
   │  provider = provider_class(api_key=GEMINI_API_KEY, model='gemini-2.0-flash-exp')
   │
   ▼
5. API Call
   │
   │  provider.chat_completion(messages, ...)
```

---

## Exception Hierarchy

```
AIServiceError (Base)
│
├─── ProviderError (Base for provider issues)
│    │
│    ├─── APIError (API communication errors)
│    │    ├─── OpenAI-specific errors
│    │    └─── Gemini-specific errors
│    │
│    └─── RateLimitError (Rate limit exceeded)
│         ├─── Automatic retry with backoff
│         └─── Logged for monitoring
│
├─── ValidationError (Input validation)
│    ├─── Content too long
│    ├─── Missing required fields
│    └─── Invalid format
│
├─── ConfigurationError (Setup issues)
│    ├─── Missing API key
│    ├─── Invalid provider name
│    └─── Model not supported
│
└─── ProviderNotFoundError (Registry lookup)
     └─── Unknown provider requested
```

---

## Package Structure

```
myapp/
├── ai_services/                      # New modular package
│   ├── __init__.py                   # Export main classes
│   │
│   ├── core/                         # Core abstractions
│   │   ├── __init__.py
│   │   ├── base.py                   # BaseAIProvider (ABC)
│   │   ├── models.py                 # ChatMessage, ChatCompletionResponse
│   │   ├── exceptions.py             # Exception hierarchy
│   │   └── registry.py               # ProviderRegistry
│   │
│   ├── providers/                    # Provider implementations
│   │   ├── __init__.py               # Auto-register providers
│   │   ├── base_provider.py          # Abstract provider interface
│   │   ├── openai_provider.py        # OpenAI implementation
│   │   └── gemini_provider.py        # Gemini implementation
│   │
│   ├── services/                     # Business logic (provider-agnostic)
│   │   ├── __init__.py
│   │   ├── base_service.py           # BaseAIService
│   │   ├── analysis.py               # AnalysisService
│   │   └── translation.py            # TranslationService
│   │
│   ├── prompts/                      # Prompt templates
│   │   ├── __init__.py
│   │   ├── base.py                   # PromptBuilder base
│   │   ├── analysis.py               # Analysis prompt templates
│   │   └── translation.py            # Translation prompt templates
│   │
│   └── config.py                     # Configuration management
│
└── books/                            # Existing Django app
    ├── utils/                        # Compatibility wrappers
    │   ├── base_ai_service.py        # DEPRECATED → ai_services.services.base_service
    │   ├── chapter_analysis.py       # DEPRECATED → ai_services.services.analysis
    │   └── chapter_translation.py    # DEPRECATED → ai_services.services.translation
    │
    ├── tasks/                        # Celery tasks
    │   ├── chapter_analysis.py       # Uses new AnalysisService
    │   └── chapter_translation.py    # Uses new TranslationService
    │
    └── models/                       # Django models
        ├── core.py                   # Chapter, Book models
        ├── context.py                # ChapterContext, BookEntity
        └── job.py                    # TranslationJob, AnalysisJob
```

---

## Migration Path

```
Current Architecture:
┌─────────────────────────────────────┐
│  ChapterTranslationService          │
│  (tightly coupled to OpenAI)        │
│                                     │
│  ├─ OpenAI client initialization   │
│  ├─ Translation logic               │
│  ├─ Prompt building                 │
│  ├─ API calls (OpenAI-specific)     │
│  └─ Response parsing                │
└─────────────────────────────────────┘
           │
           │  Can't switch providers
           │  Hard to test
           │
           ▼
    OpenAI API only


New Architecture:
┌─────────────────────────────────────┐
│  TranslationService                 │
│  (provider-agnostic)                │
│                                     │
│  ├─ Translation logic               │
│  ├─ Prompt building (templates)     │
│  ├─ Provider selection              │
│  └─ Response parsing (unified)      │
└──────────────┬──────────────────────┘
               │
               │  Delegates to provider
               │
               ▼
┌──────────────────────────────────────┐
│      ProviderRegistry                │
│                                      │
│  ├─ OpenAIProvider                  │
│  ├─ GeminiProvider                  │
│  └─ [Future: Anthropic, Cohere...]  │
└──────────────┬───────────────────────┘
               │
               │  Uses selected provider
               │
               ▼
         ┌─────────┴─────────┐
         │                   │
         ▼                   ▼
   OpenAI API          Gemini API
```

---

## Testing Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Test Pyramid                                │
└─────────────────────────────────────────────────────────────────────┘

                          ┌─────────────┐
                          │ Integration │
                          │   Tests     │
                          │  (E2E with  │
                          │   Django)   │
                          └──────┬──────┘
                                 │
                    ┌────────────┴───────────┐
                    │    Service Tests       │
                    │  (with mock providers) │
                    └────────────┬───────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              │         Provider Tests              │
              │      (unit tests, mocked API)       │
              └──────────────────┬──────────────────┘
                                 │
         ┌───────────────────────┴───────────────────────┐
         │            Core Component Tests               │
         │  (registry, exceptions, data models)          │
         └───────────────────────────────────────────────┘


Test Strategy:

1. Mock Provider (for fast unit tests):
   class MockProvider(BaseAIProvider):
       def chat_completion(self, messages, **kwargs):
           return ChatCompletionResponse(
               content='{"title": "Test", "content": "Test content"}',
               model="mock",
               provider="mock",
               finish_reason="stop",
               usage={"prompt_tokens": 10, "completion_tokens": 20}
           )

2. Real Provider Tests (with @pytest.mark.integration):
   - Skipped in CI
   - Run manually with real API keys
   - Verify actual API behavior

3. Comparison Tests (during migration):
   - Run same input through old and new implementation
   - Verify identical outputs
   - Catch regressions
```

---

## Cost Optimization Example

```
┌─────────────────────────────────────────────────────────────────────┐
│                   Cost-Optimized Configuration                      │
└─────────────────────────────────────────────────────────────────────┘

Scenario: You want to minimize costs while maintaining quality

Configuration:
┌─────────────────────────────────────────────────────────────────────┐
│ # .env                                                              │
│                                                                     │
│ # Use Gemini for analysis (cheaper, good enough)                   │
│ ANALYSIS_PROVIDER=gemini                                            │
│ GEMINI_ANALYSIS_MODEL=gemini-2.0-flash-exp                         │
│ GEMINI_API_KEY=AI...                                                │
│                                                                     │
│ # Use OpenAI for translation (better quality)                      │
│ TRANSLATION_PROVIDER=openai                                         │
│ OPENAI_TRANSLATION_MODEL=gpt-4o-mini                                │
│ OPENAI_API_KEY=sk-...                                               │
└─────────────────────────────────────────────────────────────────────┘

Cost Comparison (per 1M tokens):
┌────────────────────┬─────────────┬─────────────┬──────────────┐
│ Task               │ OpenAI      │ Gemini      │ Savings      │
├────────────────────┼─────────────┼─────────────┼──────────────┤
│ Analysis           │ $0.60       │ $0.15       │ 75% cheaper  │
│ Translation        │ $0.60       │ $0.30       │ -            │
└────────────────────┴─────────────┴─────────────┴──────────────┘

Monthly Cost (100K chapters):
┌────────────────────┬─────────────┬─────────────┬──────────────┐
│ All OpenAI         │ $1,200      │ -           │ Baseline     │
│ All Gemini         │ -           │ $450        │ 62% cheaper  │
│ Mixed (optimized)  │ $600        │ $150        │ $750 total   │
│                    │             │             │ 38% cheaper  │
└────────────────────┴─────────────┴─────────────┴──────────────┘
```

---

## Summary

This architecture provides:

1. **Flexibility** - Switch providers without code changes
2. **Testability** - Mock providers for fast unit tests
3. **Maintainability** - Clear separation of concerns
4. **Extensibility** - Easy to add new providers
5. **Cost Optimization** - Mix and match providers by task
6. **Reliability** - Unified error handling and retry logic

**Key principle:** Business logic (services) is completely independent of AI provider implementation (providers).
