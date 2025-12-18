"""
Unit tests for AI services configuration.

Tests configuration loading, validation, and provider selection.
"""
import unittest
from unittest.mock import patch
from django.test import TestCase, override_settings

from ai_services.config import AIServicesConfig
from ai_services.core.exceptions import ConfigurationError


class TestAIServicesConfig(TestCase):
    """Test configuration management"""

    @override_settings(
        AI_DEFAULT_PROVIDER="openai",
        OPENAI_API_KEY="test-openai-key",
        OPENAI_DEFAULT_MODEL="gpt-4o-mini",
        OPENAI_ANALYSIS_MAX_TOKENS=2000,
        OPENAI_ANALYSIS_TEMPERATURE=0.1,
    )
    def test_get_default_provider(self):
        """Test getting default provider"""
        provider = AIServicesConfig.get_default_provider()
        self.assertEqual(provider, "openai")

    @override_settings(
        AI_DEFAULT_PROVIDER="gemini",
        ANALYSIS_PROVIDER="openai",
    )
    def test_service_specific_provider(self):
        """Test service-specific provider override"""
        # Default is gemini
        default = AIServicesConfig.get_default_provider()
        self.assertEqual(default, "gemini")

        # But analysis uses openai
        analysis_provider = AIServicesConfig.get_provider_for_service("analysis")
        self.assertEqual(analysis_provider, "openai")

    @override_settings(
        AI_DEFAULT_PROVIDER="openai",
        OPENAI_API_KEY="test-key",
        OPENAI_DEFAULT_MODEL="gpt-4o-mini",
        OPENAI_ANALYSIS_MODEL="gpt-4o",
        OPENAI_ANALYSIS_MAX_TOKENS=3000,
        OPENAI_ANALYSIS_TEMPERATURE=0.05,
    )
    def test_get_provider_config_with_service_overrides(self):
        """Test getting provider config with service-specific overrides"""
        config = AIServicesConfig.get_provider_config("openai", "analysis")

        self.assertEqual(config["api_key"], "test-key")
        self.assertEqual(config["model"], "gpt-4o")  # Service-specific
        self.assertEqual(config["max_tokens"], 3000)  # Service-specific
        self.assertEqual(config["temperature"], 0.05)  # Service-specific

    @override_settings(
        AI_DEFAULT_PROVIDER="openai",
        OPENAI_API_KEY="test-key",
        OPENAI_DEFAULT_MODEL="gpt-4o-mini",
    )
    def test_get_provider_config_without_service(self):
        """Test getting provider config without service-specific settings"""
        config = AIServicesConfig.get_provider_config("openai")

        self.assertEqual(config["api_key"], "test-key")
        self.assertEqual(config["model"], "gpt-4o-mini")
        self.assertIsNotNone(config["max_tokens"])
        self.assertIsNotNone(config["temperature"])

    @override_settings(
        AI_DEFAULT_PROVIDER="gemini",
        GEMINI_API_KEY="test-gemini-key",
        GEMINI_DEFAULT_MODEL="gemini-2.0-flash-exp",
        GEMINI_TRANSLATION_MODEL="gemini-1.5-pro",
        GEMINI_TRANSLATION_MAX_TOKENS=20000,
    )
    def test_gemini_config(self):
        """Test Gemini provider configuration"""
        config = AIServicesConfig.get_provider_config("gemini", "translation")

        self.assertEqual(config["api_key"], "test-gemini-key")
        self.assertEqual(config["model"], "gemini-1.5-pro")
        self.assertEqual(config["max_tokens"], 20000)

    @override_settings(
        AI_DEFAULT_PROVIDER="openai",
        OPENAI_API_KEY="",  # Empty API key
    )
    def test_missing_api_key_warning(self):
        """Test that missing API key is handled"""
        with self.assertRaises(ConfigurationError) as context:
            AIServicesConfig.get_api_key("openai")

        self.assertIn("API key not configured", str(context.exception))

    @override_settings(
        AI_DEFAULT_PROVIDER="openai",
        OPENAI_API_KEY="test-key",
        OPENAI_DEFAULT_MODEL="gpt-4o-mini",
        OPENAI_ANALYSIS_MODEL="gpt-4o",
    )
    def test_get_model_hierarchy(self):
        """Test model selection hierarchy: service-specific > provider-default"""
        # Service-specific model
        analysis_model = AIServicesConfig.get_model("openai", "analysis")
        self.assertEqual(analysis_model, "gpt-4o")

        # Provider default model (no service-specific)
        translation_model = AIServicesConfig.get_model("openai", "translation")
        self.assertEqual(translation_model, "gpt-4o-mini")

        # Provider default (no service specified)
        default_model = AIServicesConfig.get_model("openai")
        self.assertEqual(default_model, "gpt-4o-mini")

    @override_settings(
        AI_DEFAULT_PROVIDER="openai",
        OPENAI_API_KEY="test-key",
        OPENAI_ANALYSIS_MAX_TOKENS=5000,
    )
    def test_get_max_tokens_hierarchy(self):
        """Test max_tokens selection hierarchy"""
        # Service-specific max_tokens
        analysis_tokens = AIServicesConfig.get_max_tokens("openai", "analysis")
        self.assertEqual(analysis_tokens, 5000)

        # Provider default (falls back to service default)
        translation_tokens = AIServicesConfig.get_max_tokens("openai", "translation")
        self.assertIsNotNone(translation_tokens)
        self.assertGreater(translation_tokens, 0)

    @override_settings(
        AI_DEFAULT_PROVIDER="openai",
        OPENAI_API_KEY="test-key",
        OPENAI_ANALYSIS_TEMPERATURE=0.05,
        OPENAI_TRANSLATION_TEMPERATURE=0.3,
    )
    def test_get_temperature_hierarchy(self):
        """Test temperature selection hierarchy"""
        analysis_temp = AIServicesConfig.get_temperature("openai", "analysis")
        self.assertEqual(analysis_temp, 0.05)

        translation_temp = AIServicesConfig.get_temperature("openai", "translation")
        self.assertEqual(translation_temp, 0.3)


class TestConfigurationEdgeCases(TestCase):
    """Test configuration edge cases"""

    @override_settings()
    def test_fallback_to_env_variables(self):
        """Test that configuration falls back to environment variables"""
        with patch.dict('os.environ', {
            'AI_DEFAULT_PROVIDER': 'gemini',
            'GEMINI_API_KEY': 'env-gemini-key',
        }):
            provider = AIServicesConfig.get_default_provider()
            self.assertEqual(provider, "gemini")

    @override_settings(
        AI_DEFAULT_PROVIDER="openai",
        OPENAI_API_KEY="test-key",
    )
    def test_unknown_service(self):
        """Test configuration for unknown service uses defaults"""
        provider = AIServicesConfig.get_provider_for_service("unknown_service")
        # Should fall back to default provider
        self.assertEqual(provider, "openai")

    @override_settings(
        AI_DEFAULT_PROVIDER="openai",
        OPENAI_API_KEY="test-key",
        OPENAI_DEFAULT_MODEL="gpt-4o-mini",
    )
    def test_config_caching(self):
        """Test that configuration is efficiently accessed"""
        # Multiple calls should work without errors
        config1 = AIServicesConfig.get_provider_config("openai", "analysis")
        config2 = AIServicesConfig.get_provider_config("openai", "analysis")

        self.assertEqual(config1["api_key"], config2["api_key"])
        self.assertEqual(config1["model"], config2["model"])


class TestProviderSelection(TestCase):
    """Test provider selection logic"""

    @override_settings(
        AI_DEFAULT_PROVIDER="openai",
        ANALYSIS_PROVIDER="gemini",
        TRANSLATION_PROVIDER="openai",
    )
    def test_mixed_provider_configuration(self):
        """Test that different services can use different providers"""
        default = AIServicesConfig.get_default_provider()
        analysis = AIServicesConfig.get_provider_for_service("analysis")
        translation = AIServicesConfig.get_provider_for_service("translation")

        self.assertEqual(default, "openai")
        self.assertEqual(analysis, "gemini")
        self.assertEqual(translation, "openai")

    @override_settings(
        AI_DEFAULT_PROVIDER="gemini",
    )
    def test_all_services_use_default(self):
        """Test that services use default provider when not overridden"""
        analysis = AIServicesConfig.get_provider_for_service("analysis")
        translation = AIServicesConfig.get_provider_for_service("translation")

        self.assertEqual(analysis, "gemini")
        self.assertEqual(translation, "gemini")


if __name__ == "__main__":
    unittest.main()
