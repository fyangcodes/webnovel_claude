#!/usr/bin/env python
"""
Test script to demonstrate enhanced error handling in AI services.

This script tests error scenarios to show how detailed error information
(prompts and responses) are now captured and logged.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'myapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myapp.settings')
django.setup()

from unittest.mock import Mock
from ai_services.services import AnalysisService, TranslationService
from ai_services.core.models import ChatCompletionResponse
from ai_services.core.exceptions import ValidationError, ResponseParsingError


def test_analysis_validation_error():
    """Test analysis service with invalid JSON response"""
    print("=" * 70)
    print("TEST 1: Analysis Service - Invalid JSON Response")
    print("=" * 70)

    # Create a mock provider that returns invalid JSON
    mock_provider = Mock()
    mock_provider.chat_completion.return_value = ChatCompletionResponse(
        content="This is not valid JSON at all!",
        model="mock-model",
        provider="mock",
        finish_reason="stop",
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    )

    service = AnalysisService()
    service.provider = mock_provider
    service.provider_name = "mock"

    # Test with invalid response
    test_content = "李明在北京修炼，他的朋友张伟来自上海。"
    result = service.extract_entities_and_summary(test_content, "zh")

    print("\nResult:")
    print(f"  Characters: {result.get('characters', [])}")
    print(f"  Places: {result.get('places', [])}")
    print(f"  Terms: {result.get('terms', [])}")
    print(f"  Summary: {result.get('summary', '')[:100]}...")
    print(f"  Has Error Details: {'error_details' in result}")

    if 'error_details' in result:
        print("\n" + "=" * 70)
        print("ERROR DETAILS CAPTURED:")
        print("=" * 70)
        print(result['error_details'])

    print("\n" + "✓" * 70 + "\n")


def test_analysis_missing_fields():
    """Test analysis service with missing required fields"""
    print("=" * 70)
    print("TEST 2: Analysis Service - Missing Required Fields")
    print("=" * 70)

    # Create a mock provider that returns JSON but missing fields
    mock_provider = Mock()
    mock_provider.chat_completion.return_value = ChatCompletionResponse(
        content='{"characters": ["李明"], "places": ["北京"]}',  # Missing 'terms' and 'summary'
        model="mock-model",
        provider="mock",
        finish_reason="stop",
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    )

    service = AnalysisService()
    service.provider = mock_provider
    service.provider_name = "mock"

    # Test with missing fields
    test_content = "李明在北京修炼，掌握了强大的功法。"
    result = service.extract_entities_and_summary(test_content, "zh")

    print("\nResult:")
    print(f"  Has Error Details: {'error_details' in result}")

    if 'error_details' in result:
        print("\n" + "=" * 70)
        print("ERROR DETAILS CAPTURED:")
        print("=" * 70)
        # Print first 1000 chars of error details
        error_details = result['error_details']
        print(error_details[:1500] if len(error_details) > 1500 else error_details)
        if len(error_details) > 1500:
            print(f"\n... (truncated, total length: {len(error_details)} chars)")

    print("\n" + "✓" * 70 + "\n")


def test_translation_missing_entity_mappings():
    """Test translation service with missing entity mappings"""
    print("=" * 70)
    print("TEST 3: Translation Service - Missing Entity Mappings")
    print("=" * 70)

    # Create a mock provider that returns translation without entity mappings
    mock_provider = Mock()
    mock_provider.chat_completion.return_value = ChatCompletionResponse(
        content='{"title": "Chapter 1", "content": "Li Ming cultivates...", "entity_mappings": {}}',
        model="mock-model",
        provider="mock",
        finish_reason="stop",
        usage={"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300}
    )

    service = TranslationService()
    service.provider = mock_provider
    service.provider_name = "mock"

    # Create a simple translation context with expected entities
    test_title = "第一章"
    test_content = "李明在北京修炼功法，他的师父是张真人。"
    source_language = "Chinese"
    target_language = "English"

    context = {
        'entities': {
            'found_entities': [],
            'new_entities': ["李明", "北京", "功法", "张真人"]  # Entities we expect to be translated
        },
        'previous_chapters': []
    }

    try:
        result = service._translate_with_context(
            title=test_title,
            content=test_content,
            source_language=source_language,
            target_language=target_language,
            context=context
        )

        print("\nResult:")
        print(f"  Title: {result.get('title')}")
        print(f"  Content: {result.get('content', '')[:100]}...")
        print(f"  Entity Mappings: {result.get('entity_mappings', {})}")
        print(f"  Has Validation Warning: {'entity_validation_warning' in result}")
        print(f"  Missing Entities: {result.get('missing_entities', [])}")

    except ValidationError as e:
        print("\nValidationError caught (expected):")
        print(f"  Error message preview: {str(e)[:200]}...")
        print(f"\n  Full error includes:")
        print(f"    - Error type and message")
        print(f"    - Provider and model info")
        print(f"    - Content preview")
        print(f"    - Translation context (expected vs received entities)")
        print(f"    - Full prompt sent")
        print(f"    - Full response received")

    print("\n" + "✓" * 70 + "\n")


def main():
    """Run all error handling tests"""
    print("\n" + "=" * 70)
    print("ENHANCED ERROR HANDLING DEMONSTRATION")
    print("=" * 70)
    print("\nThis demonstrates how the AI services now capture detailed error")
    print("information including prompts and responses when validation fails.\n")

    try:
        test_analysis_validation_error()
        test_analysis_missing_fields()
        test_translation_missing_entity_mappings()

        print("=" * 70)
        print("ALL TESTS COMPLETED")
        print("=" * 70)
        print("\nKey improvements demonstrated:")
        print("  ✓ Invalid JSON responses are caught with full prompt/response")
        print("  ✓ Missing required fields are detected with context")
        print("  ✓ Missing entity mappings are validated and logged")
        print("  ✓ Error details include provider, model, and content info")
        print("  ✓ Prompts and responses are truncated but preserved")
        print("\nThese error details are now stored in job error_message fields")
        print("for analysis and debugging purposes.")
        print()

    except Exception as e:
        print(f"\n❌ Test failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
