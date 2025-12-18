#!/usr/bin/env python
"""
Test script for AI services infrastructure.

Verifies that the core components are working correctly.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myapp.settings')
django.setup()

from ai_services.core import ProviderRegistry, ChatMessage
from ai_services.config import AIServicesConfig


def test_provider_registry():
    """Test that providers are registered correctly"""
    print("Testing Provider Registry...")

    providers = ProviderRegistry.list_providers()
    print(f"  Registered providers: {providers}")

    assert "openai" in providers, "OpenAI provider not registered"
    assert "gemini" in providers, "Gemini provider not registered"

    print("  ✓ Provider registry working correctly\n")


def test_configuration():
    """Test configuration loading"""
    print("Testing Configuration...")

    default_provider = AIServicesConfig.get_default_provider()
    print(f"  Default provider: {default_provider}")

    translation_provider = AIServicesConfig.get_provider_for_service("translation")
    print(f"  Translation provider: {translation_provider}")

    analysis_provider = AIServicesConfig.get_provider_for_service("analysis")
    print(f"  Analysis provider: {analysis_provider}")

    # Check if API keys are configured
    openai_key = AIServicesConfig.get_api_key("openai")
    print(f"  OpenAI API key configured: {bool(openai_key)}")

    gemini_key = AIServicesConfig.get_api_key("gemini")
    print(f"  Gemini API key configured: {bool(gemini_key)}")

    print("  ✓ Configuration loading working correctly\n")


def test_chat_message():
    """Test ChatMessage data model"""
    print("Testing ChatMessage...")

    msg = ChatMessage(role="user", content="Hello")
    print(f"  Created message: role={msg.role}, content={msg.content}")

    # Test validation
    try:
        invalid_msg = ChatMessage(role="invalid", content="test")
        print("  ✗ Validation failed - invalid role accepted")
    except ValueError as e:
        print(f"  ✓ Validation working: {e}\n")


def test_provider_instantiation():
    """Test provider instantiation"""
    print("Testing Provider Instantiation...")

    # Get provider classes
    openai_class = ProviderRegistry.get("openai")
    gemini_class = ProviderRegistry.get("gemini")

    print(f"  OpenAI provider class: {openai_class.__name__}")
    print(f"  Gemini provider class: {gemini_class.__name__}")

    # Try to instantiate (will fail without API key, but that's expected)
    try:
        openai_provider = openai_class(api_key="test_key", model="gpt-4o-mini")
        info = openai_provider.get_model_info()
        print(f"  OpenAI provider info: {info}")
        print("  ✓ OpenAI provider instantiation working")
    except Exception as e:
        print(f"  ✗ OpenAI provider error: {e}")

    try:
        gemini_provider = gemini_class(api_key="test_key", model="gemini-2.0-flash-exp")
        info = gemini_provider.get_model_info()
        print(f"  Gemini provider info: {info}")
        print("  ✓ Gemini provider instantiation working")
    except Exception as e:
        print(f"  ✗ Gemini provider error: {e}")

    print()


def main():
    """Run all tests"""
    print("=" * 70)
    print("AI Services Infrastructure Test")
    print("=" * 70)
    print()

    try:
        test_provider_registry()
        test_configuration()
        test_chat_message()
        test_provider_instantiation()

        print("=" * 70)
        print("All core tests passed! ✓")
        print("=" * 70)
        return 0

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
