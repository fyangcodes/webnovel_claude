"""
Unit tests for AI providers (OpenAI and Gemini).

Tests provider implementations with mocked API responses.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from ai_services.core.models import ChatMessage, ChatCompletionResponse
from ai_services.core.exceptions import (
    APIError,
    RateLimitError,
    ValidationError,
    ResponseParsingError,
)
from ai_services.providers.openai_provider import OpenAIProvider
from ai_services.providers.gemini_provider import GeminiProvider


class TestOpenAIProvider(unittest.TestCase):
    """Test OpenAI provider implementation"""

    def setUp(self):
        """Set up test fixtures"""
        self.api_key = "test-openai-key"
        self.model = "gpt-4o-mini"

    @patch('ai_services.providers.openai_provider.OpenAI')
    def test_initialization(self, mock_openai_class):
        """Test provider initialization"""
        provider = OpenAIProvider(api_key=self.api_key, model=self.model)

        self.assertEqual(provider.model, self.model)
        self.assertIsNotNone(provider.client)
        mock_openai_class.assert_called_once_with(api_key=self.api_key)

    @patch('ai_services.providers.openai_provider.OpenAI')
    def test_chat_completion_success(self, mock_openai_class):
        """Test successful chat completion"""
        # Mock OpenAI response
        mock_choice = Mock()
        mock_choice.message.content = '{"characters": ["李明"], "summary": "Test summary"}'
        mock_choice.finish_reason = "stop"

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.model = self.model
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        # Create provider and test
        provider = OpenAIProvider(api_key=self.api_key, model=self.model)
        messages = [
            ChatMessage(role="system", content="You are a helpful assistant"),
            ChatMessage(role="user", content="Analyze this text")
        ]

        response = provider.chat_completion(messages, max_tokens=1000, temperature=0.1)

        # Verify response
        self.assertIsInstance(response, ChatCompletionResponse)
        self.assertEqual(response.content, '{"characters": ["李明"], "summary": "Test summary"}')
        self.assertEqual(response.model, self.model)
        self.assertEqual(response.provider, "openai")
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.usage["prompt_tokens"], 100)
        self.assertEqual(response.usage["completion_tokens"], 50)
        self.assertEqual(response.usage["total_tokens"], 150)

        # Verify API was called correctly
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_kwargs["model"], self.model)
        self.assertEqual(call_kwargs["max_tokens"], 1000)
        self.assertEqual(call_kwargs["temperature"], 0.1)
        self.assertEqual(len(call_kwargs["messages"]), 2)

    @patch('ai_services.providers.openai_provider.OpenAI')
    def test_chat_completion_with_json_format(self, mock_openai_class):
        """Test chat completion with JSON response format"""
        mock_choice = Mock()
        mock_choice.message.content = '{"result": "test"}'
        mock_choice.finish_reason = "stop"

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.model = self.model
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 25
        mock_response.usage.total_tokens = 75

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(api_key=self.api_key, model=self.model)
        messages = [ChatMessage(role="user", content="Test")]

        response = provider.chat_completion(messages, response_format="json")

        # Verify JSON format was requested
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_kwargs["response_format"], {"type": "json_object"})

    @patch('ai_services.providers.openai_provider.OpenAI')
    def test_rate_limit_error(self, mock_openai_class):
        """Test rate limit error handling"""
        mock_client = Mock()

        # Simulate rate limit error
        from openai import RateLimitError as OpenAIRateLimitError
        mock_client.chat.completions.create.side_effect = OpenAIRateLimitError(
            message="Rate limit exceeded",
            response=Mock(status_code=429),
            body=None
        )
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(api_key=self.api_key, model=self.model)
        messages = [ChatMessage(role="user", content="Test")]

        with self.assertRaises(RateLimitError) as context:
            provider.chat_completion(messages)

        self.assertIn("Rate limit exceeded", str(context.exception))

    @patch('ai_services.providers.openai_provider.OpenAI')
    def test_api_error(self, mock_openai_class):
        """Test API error handling"""
        mock_client = Mock()

        # Simulate API error
        from openai import APIError as OpenAIAPIError
        mock_client.chat.completions.create.side_effect = OpenAIAPIError(
            message="API error occurred",
            request=Mock(),
            body=None
        )
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(api_key=self.api_key, model=self.model)
        messages = [ChatMessage(role="user", content="Test")]

        with self.assertRaises(APIError) as context:
            provider.chat_completion(messages)

        self.assertIn("OpenAI API error", str(context.exception))


class TestGeminiProvider(unittest.TestCase):
    """Test Gemini provider implementation"""

    def setUp(self):
        """Set up test fixtures"""
        self.api_key = "test-gemini-key"
        self.model_name = "gemini-2.0-flash-exp"

    @patch('ai_services.providers.gemini_provider.genai')
    def test_initialization(self, mock_genai):
        """Test provider initialization"""
        provider = GeminiProvider(api_key=self.api_key, model=self.model_name)

        self.assertEqual(provider.model_name, self.model_name)
        mock_genai.configure.assert_called_once_with(api_key=self.api_key)

    @patch('ai_services.providers.gemini_provider.genai')
    def test_chat_completion_success(self, mock_genai):
        """Test successful chat completion"""
        # Mock Gemini response
        mock_response = Mock()
        mock_response.text = '{"characters": ["李明"], "summary": "Test summary"}'
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_response.usage_metadata.total_token_count = 150

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        # Create provider and test
        provider = GeminiProvider(api_key=self.api_key, model=self.model_name)
        messages = [
            ChatMessage(role="system", content="You are a helpful assistant"),
            ChatMessage(role="user", content="Analyze this text")
        ]

        response = provider.chat_completion(messages, max_tokens=1000, temperature=0.1)

        # Verify response
        self.assertIsInstance(response, ChatCompletionResponse)
        self.assertEqual(response.content, '{"characters": ["李明"], "summary": "Test summary"}')
        self.assertEqual(response.model, self.model_name)
        self.assertEqual(response.provider, "gemini")
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.usage["prompt_tokens"], 100)
        self.assertEqual(response.usage["completion_tokens"], 50)
        self.assertEqual(response.usage["total_tokens"], 150)

    @patch('ai_services.providers.gemini_provider.genai')
    def test_system_message_handling(self, mock_genai):
        """Test that system messages are properly handled"""
        mock_response = Mock()
        mock_response.text = "Response"
        mock_response.usage_metadata.prompt_token_count = 50
        mock_response.usage_metadata.candidates_token_count = 25
        mock_response.usage_metadata.total_token_count = 75

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider(api_key=self.api_key, model=self.model_name)
        messages = [
            ChatMessage(role="system", content="System instruction 1"),
            ChatMessage(role="system", content="System instruction 2"),
            ChatMessage(role="user", content="User message")
        ]

        response = provider.chat_completion(messages)

        # Verify system instructions were combined
        call_args = mock_genai.GenerativeModel.call_args[1]
        self.assertIn("system_instruction", call_args)
        system_instruction = call_args["system_instruction"]
        self.assertIn("System instruction 1", system_instruction)
        self.assertIn("System instruction 2", system_instruction)

    @patch('ai_services.providers.gemini_provider.genai')
    def test_json_format_request(self, mock_genai):
        """Test JSON format configuration"""
        mock_response = Mock()
        mock_response.text = '{"result": "test"}'
        mock_response.usage_metadata.prompt_token_count = 30
        mock_response.usage_metadata.candidates_token_count = 15
        mock_response.usage_metadata.total_token_count = 45

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider(api_key=self.api_key, model=self.model_name)
        messages = [ChatMessage(role="user", content="Test")]

        response = provider.chat_completion(messages, response_format="json")

        # Verify generation config includes JSON mime type
        call_kwargs = mock_model.generate_content.call_args[1]
        self.assertIn("generation_config", call_kwargs)
        self.assertEqual(
            call_kwargs["generation_config"]["response_mime_type"],
            "application/json"
        )

    @patch('ai_services.providers.gemini_provider.genai')
    def test_rate_limit_error(self, mock_genai):
        """Test rate limit error handling"""
        mock_model = Mock()

        # Simulate rate limit error (429)
        error = Exception("429 Resource exhausted")
        mock_model.generate_content.side_effect = error
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider(api_key=self.api_key, model=self.model_name)
        messages = [ChatMessage(role="user", content="Test")]

        with self.assertRaises(RateLimitError) as context:
            provider.chat_completion(messages)

        self.assertIn("Rate limit", str(context.exception))

    @patch('ai_services.providers.gemini_provider.genai')
    def test_api_error(self, mock_genai):
        """Test API error handling"""
        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception("API connection failed")
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider(api_key=self.api_key, model=self.model_name)
        messages = [ChatMessage(role="user", content="Test")]

        with self.assertRaises(APIError) as context:
            provider.chat_completion(messages)

        self.assertIn("Gemini API error", str(context.exception))

    @patch('ai_services.providers.gemini_provider.genai')
    def test_blocked_content_error(self, mock_genai):
        """Test blocked content handling"""
        mock_response = Mock()
        mock_response.text = None  # No text when blocked
        mock_response.prompt_feedback.block_reason = "SAFETY"

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider(api_key=self.api_key, model=self.model_name)
        messages = [ChatMessage(role="user", content="Test")]

        with self.assertRaises(ResponseParsingError) as context:
            provider.chat_completion(messages)

        self.assertIn("blocked", str(context.exception).lower())


class TestProviderComparison(unittest.TestCase):
    """Test that both providers produce compatible outputs"""

    @patch('ai_services.providers.openai_provider.OpenAI')
    @patch('ai_services.providers.gemini_provider.genai')
    def test_response_format_compatibility(self, mock_gemini, mock_openai_class):
        """Test that both providers return compatible response formats"""
        test_content = '{"test": "data"}'

        # Mock OpenAI
        mock_openai_choice = Mock()
        mock_openai_choice.message.content = test_content
        mock_openai_choice.finish_reason = "stop"
        mock_openai_response = Mock()
        mock_openai_response.choices = [mock_openai_choice]
        mock_openai_response.model = "gpt-4o-mini"
        mock_openai_response.usage.prompt_tokens = 100
        mock_openai_response.usage.completion_tokens = 50
        mock_openai_response.usage.total_tokens = 150

        mock_openai_client = Mock()
        mock_openai_client.chat.completions.create.return_value = mock_openai_response
        mock_openai_class.return_value = mock_openai_client

        # Mock Gemini
        mock_gemini_response = Mock()
        mock_gemini_response.text = test_content
        mock_gemini_response.usage_metadata.prompt_token_count = 100
        mock_gemini_response.usage_metadata.candidates_token_count = 50
        mock_gemini_response.usage_metadata.total_token_count = 150

        mock_gemini_model = Mock()
        mock_gemini_model.generate_content.return_value = mock_gemini_response
        mock_gemini.GenerativeModel.return_value = mock_gemini_model

        # Test both providers
        openai_provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")
        gemini_provider = GeminiProvider(api_key="test", model="gemini-2.0-flash-exp")

        messages = [ChatMessage(role="user", content="Test")]

        openai_response = openai_provider.chat_completion(messages)
        gemini_response = gemini_provider.chat_completion(messages)

        # Verify both have same structure
        self.assertEqual(type(openai_response), type(gemini_response))
        self.assertEqual(openai_response.content, gemini_response.content)
        self.assertEqual(openai_response.finish_reason, gemini_response.finish_reason)
        self.assertEqual(openai_response.usage["total_tokens"], gemini_response.usage["total_tokens"])


if __name__ == "__main__":
    unittest.main()
