"""
Unit tests for AI services (Analysis and Translation).

Tests service implementations with mocked providers.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model

from ai_services.core.models import ChatMessage, ChatCompletionResponse
from ai_services.core.exceptions import (
    ValidationError,
    ResponseParsingError,
    APIError,
)
from ai_services.services import AnalysisService, TranslationService
from books.models import Language, BookMaster, Book, Chapter, ChapterMaster

User = get_user_model()


class MockProvider:
    """Mock provider for testing services"""

    def __init__(self, response_content, **kwargs):
        self.response_content = response_content
        self.model = kwargs.get('model', 'mock-model')
        self.call_count = 0
        self.last_messages = None
        self.last_kwargs = None

    def chat_completion(self, messages, **kwargs):
        """Mock chat completion"""
        self.call_count += 1
        self.last_messages = messages
        self.last_kwargs = kwargs

        return ChatCompletionResponse(
            content=self.response_content,
            model=self.model,
            provider="mock",
            finish_reason="stop",
            usage={
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
            raw_response=None,
        )


class TestAnalysisService(unittest.TestCase):
    """Test AnalysisService with mocked provider"""

    def test_initialization_default_provider(self):
        """Test service initialization with default provider"""
        with patch('ai_services.services.base_service.AIServicesConfig') as mock_config:
            mock_config.get_default_provider.return_value = "openai"
            mock_config.get_provider_config.return_value = {
                "api_key": "test-key",
                "model": "gpt-4o-mini",
                "max_tokens": 2000,
                "temperature": 0.1,
            }

            with patch('ai_services.services.base_service.ProviderRegistry') as mock_registry:
                mock_provider_class = Mock()
                mock_registry.get.return_value = mock_provider_class

                service = AnalysisService()

                mock_registry.get.assert_called_once_with("openai")
                mock_provider_class.assert_called_once()

    def test_extract_entities_success(self):
        """Test successful entity extraction"""
        mock_response = '''
        {
            "characters": ["李明", "张伟"],
            "places": ["北京", "上海"],
            "terms": ["修炼", "功法"],
            "summary": "这是一个关于修炼的故事。"
        }
        '''

        mock_provider = MockProvider(mock_response)
        service = AnalysisService()
        service.provider = mock_provider

        result = service.extract_entities_and_summary(
            content="李明在北京修炼功法...",
            language_code="zh"
        )

        # Verify result structure
        self.assertEqual(len(result["characters"]), 2)
        self.assertIn("李明", result["characters"])
        self.assertIn("张伟", result["characters"])
        self.assertEqual(len(result["places"]), 2)
        self.assertEqual(len(result["terms"]), 2)
        self.assertEqual(result["summary"], "这是一个关于修炼的故事。")

        # Verify provider was called
        self.assertEqual(mock_provider.call_count, 1)
        self.assertEqual(len(mock_provider.last_messages), 1)
        self.assertEqual(mock_provider.last_kwargs["max_tokens"], 2000)
        self.assertEqual(mock_provider.last_kwargs["temperature"], 0.1)
        self.assertEqual(mock_provider.last_kwargs["response_format"], "json")

    def test_extract_entities_with_retry(self):
        """Test entity extraction with retry on API error"""
        # First call fails, second succeeds
        call_count = [0]

        def mock_completion(messages, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise APIError("Temporary error")
            return ChatCompletionResponse(
                content='{"characters": [], "places": [], "terms": [], "summary": "Test"}',
                model="mock",
                provider="mock",
                finish_reason="stop",
                usage={"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
            )

        mock_provider = Mock()
        mock_provider.chat_completion = mock_completion

        service = AnalysisService()
        service.provider = mock_provider
        service.max_retries = 2

        result = service.extract_entities_and_summary("Test content", "zh")

        # Verify retry worked
        self.assertEqual(call_count[0], 2)
        self.assertIn("summary", result)

    def test_extract_entities_invalid_json(self):
        """Test handling of invalid JSON response"""
        mock_provider = MockProvider("This is not valid JSON")
        service = AnalysisService()
        service.provider = mock_provider

        with self.assertRaises(ResponseParsingError) as context:
            service.extract_entities_and_summary("Test content", "zh")

        self.assertIn("Invalid JSON", str(context.exception))

    def test_extract_entities_missing_fields(self):
        """Test handling of response with missing fields"""
        mock_response = '{"characters": ["Test"]}'  # Missing other fields

        mock_provider = MockProvider(mock_response)
        service = AnalysisService()
        service.provider = mock_provider

        with self.assertRaises(ValidationError) as context:
            service.extract_entities_and_summary("Test content", "zh")

        self.assertIn("Missing required field", str(context.exception))

    def test_entity_name_cleaning(self):
        """Test entity name cleaning (removing leading numbers)"""
        mock_response = '''
        {
            "characters": ["1. 李明", "2. 张伟"],
            "places": ["1. 北京"],
            "terms": ["1. 修炼"],
            "summary": "Test"
        }
        '''

        mock_provider = MockProvider(mock_response)
        service = AnalysisService()
        service.provider = mock_provider

        result = service.extract_entities_and_summary("Test", "zh")

        # Verify names were cleaned
        self.assertEqual(result["characters"], ["李明", "张伟"])
        self.assertEqual(result["places"], ["北京"])
        self.assertEqual(result["terms"], ["修炼"])


class TestTranslationServiceUnit(TestCase):
    """Test TranslationService with mocked provider (using Django TestCase for DB)"""

    def setUp(self):
        """Set up test data"""
        # Create user
        self.user = User.objects.create_user(username="testuser", password="testpass")

        # Create languages
        self.zh = Language.objects.create(
            code="zh",
            name="Chinese",
            local_name="中文",
            count_units="CHARS",
            wpm=200
        )
        self.en = Language.objects.create(
            code="en",
            name="English",
            local_name="English",
            count_units="WORDS",
            wpm=200
        )

        # Create book structure
        self.bookmaster = BookMaster.objects.create(
            canonical_title="Test Novel",
            owner=self.user,
            original_language=self.zh
        )

        self.zh_book = Book.objects.create(
            bookmaster=self.bookmaster,
            title="测试小说",
            language=self.zh,
            is_public=True
        )

        self.chaptermaster = ChapterMaster.objects.create(
            bookmaster=self.bookmaster,
            canonical_title="Chapter 1",
            chapter_number=1
        )

        self.zh_chapter = Chapter.objects.create(
            chaptermaster=self.chaptermaster,
            book=self.zh_book,
            title="第一章",
            content="李明在北京修炼...",
            slug="chapter-1",
            is_public=True
        )

    def test_translate_chapter_success(self):
        """Test successful chapter translation"""
        mock_response = '''
        {
            "title": "Chapter 1",
            "content": "Li Ming cultivates in Beijing...",
            "entity_mappings": {
                "李明": "Li Ming",
                "北京": "Beijing"
            }
        }
        '''

        mock_provider = MockProvider(mock_response)
        service = TranslationService()
        service.provider = mock_provider

        translated_chapter = service.translate_chapter(self.zh_chapter, "en")

        # Verify translated chapter
        self.assertIsNotNone(translated_chapter)
        self.assertEqual(translated_chapter.title, "Chapter 1")
        self.assertEqual(translated_chapter.content, "Li Ming cultivates in Beijing...")
        self.assertEqual(translated_chapter.book.language.code, "en")
        self.assertEqual(translated_chapter.chaptermaster, self.chaptermaster)

        # Verify provider was called
        self.assertEqual(mock_provider.call_count, 1)

    def test_translate_chapter_validation_error(self):
        """Test translation with empty content"""
        empty_chapter = Chapter.objects.create(
            chaptermaster=self.chaptermaster,
            book=self.zh_book,
            title="Empty",
            content="",
            slug="empty"
        )

        service = TranslationService()

        with self.assertRaises(ValidationError) as context:
            service.translate_chapter(empty_chapter, "en")

        self.assertIn("cannot be empty", str(context.exception))

    def test_translate_chapter_same_language(self):
        """Test translating to same language raises error"""
        service = TranslationService()

        with self.assertRaises(ValidationError) as context:
            service.translate_chapter(self.zh_chapter, "zh")

        self.assertIn("same as source", str(context.exception))

    def test_translate_chapter_missing_fields(self):
        """Test handling of response with missing required fields"""
        mock_response = '{"title": "Test"}'  # Missing content

        mock_provider = MockProvider(mock_response)
        service = TranslationService()
        service.provider = mock_provider

        with self.assertRaises(ResponseParsingError) as context:
            service.translate_chapter(self.zh_chapter, "en")

        self.assertIn("Missing required field", str(context.exception))

    def test_context_gathering(self):
        """Test that translation gathers context from previous chapters"""
        # Create a second chapter
        chaptermaster2 = ChapterMaster.objects.create(
            bookmaster=self.bookmaster,
            canonical_title="Chapter 2",
            chapter_number=2
        )
        zh_chapter2 = Chapter.objects.create(
            chaptermaster=chaptermaster2,
            book=self.zh_book,
            title="第二章",
            content="李明继续修炼...",
            slug="chapter-2",
            is_public=True
        )

        mock_response = '''
        {
            "title": "Chapter 2",
            "content": "Li Ming continues...",
            "entity_mappings": {}
        }
        '''

        mock_provider = MockProvider(mock_response)
        service = TranslationService()
        service.provider = mock_provider

        service.translate_chapter(zh_chapter2, "en")

        # Verify provider received context (check messages include previous chapter info)
        messages = mock_provider.last_messages
        prompt_content = messages[0].content

        # Should mention previous chapters
        self.assertIn("previous", prompt_content.lower())


class TestServiceProviderSwitching(unittest.TestCase):
    """Test that services can switch between providers"""

    @patch('ai_services.services.base_service.ProviderRegistry')
    def test_explicit_provider_selection(self, mock_registry):
        """Test explicitly specifying a provider"""
        mock_openai_class = Mock()
        mock_gemini_class = Mock()

        def get_provider(name):
            if name == "openai":
                return mock_openai_class
            elif name == "gemini":
                return mock_gemini_class
            raise ValueError(f"Unknown provider: {name}")

        mock_registry.get = get_provider

        # Test OpenAI selection
        service1 = AnalysisService(provider_name="openai", api_key="test", model="gpt-4o-mini")
        mock_openai_class.assert_called()

        # Test Gemini selection
        service2 = AnalysisService(provider_name="gemini", api_key="test", model="gemini-2.0-flash-exp")
        mock_gemini_class.assert_called()


if __name__ == "__main__":
    unittest.main()
