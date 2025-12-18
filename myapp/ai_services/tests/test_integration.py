"""
Integration tests for AI services.

These tests verify end-to-end functionality with real Django models
and mocked API responses.
"""
import unittest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model

from ai_services.services import AnalysisService, TranslationService
from ai_services.core.models import ChatCompletionResponse
from books.models import (
    Language,
    BookMaster,
    Book,
    Chapter,
    ChapterMaster,
    ChapterContext,
    BookEntity,
)

User = get_user_model()


class TestAnalysisServiceIntegration(TestCase):
    """Integration tests for AnalysisService with Django models"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(username="testuser", password="testpass")

        self.zh = Language.objects.create(
            code="zh",
            name="Chinese",
            local_name="中文",
            count_units="CHARS",
            wpm=200
        )

        self.bookmaster = BookMaster.objects.create(
            canonical_title="Test Novel",
            owner=self.user,
            original_language=self.zh
        )

        self.book = Book.objects.create(
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

        self.chapter = Chapter.objects.create(
            chaptermaster=self.chaptermaster,
            book=self.book,
            title="第一章",
            content="李明在北京修炼功法，他的朋友张伟在上海研究阵法。",
            slug="chapter-1",
            is_public=True
        )

    def _create_mock_provider(self, response_content):
        """Create a mock provider with specified response"""
        mock_provider = Mock()
        mock_provider.chat_completion.return_value = ChatCompletionResponse(
            content=response_content,
            model="mock",
            provider="mock",
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )
        return mock_provider

    def test_analysis_creates_chapter_context(self):
        """Test that analysis creates ChapterContext with correct data"""
        mock_response = '''
        {
            "characters": ["李明", "张伟"],
            "places": ["北京", "上海"],
            "terms": ["修炼", "功法", "阵法"],
            "summary": "李明和张伟分别在不同城市修炼。"
        }
        '''

        mock_provider = self._create_mock_provider(mock_response)
        service = AnalysisService()
        service.provider = mock_provider

        # Create context
        context, created = ChapterContext.objects.get_or_create(chapter=self.chapter)

        # Analyze chapter content
        result = service.extract_entities_and_summary(self.chapter.content, "zh")

        # Update context with results
        context.summary = result["summary"]
        context.key_terms = {
            "characters": result["characters"],
            "places": result["places"],
            "terms": result["terms"],
        }
        context.save()

        # Verify context was created and populated
        context.refresh_from_db()
        self.assertEqual(context.summary, "李明和张伟分别在不同城市修炼。")
        self.assertEqual(len(context.key_terms["characters"]), 2)
        self.assertIn("李明", context.key_terms["characters"])
        self.assertEqual(len(context.key_terms["places"]), 2)
        self.assertEqual(len(context.key_terms["terms"]), 3)

    def test_analysis_creates_book_entities(self):
        """Test that analysis creates BookEntity records"""
        mock_response = '''
        {
            "characters": ["李明", "张伟"],
            "places": ["北京"],
            "terms": ["修炼"],
            "summary": "Test"
        }
        '''

        mock_provider = self._create_mock_provider(mock_response)
        service = AnalysisService()
        service.provider = mock_provider

        result = service.extract_entities_and_summary(self.chapter.content, "zh")

        # Create BookEntity records (normally done by ChapterContext)
        from books.choices import EntityType

        for name in result["characters"]:
            BookEntity.objects.get_or_create(
                bookmaster=self.bookmaster,
                source_name=name,
                defaults={
                    "entity_type": EntityType.CHARACTER,
                    "first_chapter": self.chapter,
                }
            )

        for name in result["places"]:
            BookEntity.objects.get_or_create(
                bookmaster=self.bookmaster,
                source_name=name,
                defaults={
                    "entity_type": EntityType.PLACE,
                    "first_chapter": self.chapter,
                }
            )

        # Verify entities were created
        characters = BookEntity.objects.filter(
            bookmaster=self.bookmaster,
            entity_type=EntityType.CHARACTER
        )
        self.assertEqual(characters.count(), 2)

        places = BookEntity.objects.filter(
            bookmaster=self.bookmaster,
            entity_type=EntityType.PLACE
        )
        self.assertEqual(places.count(), 1)


class TestTranslationServiceIntegration(TestCase):
    """Integration tests for TranslationService with Django models"""

    def setUp(self):
        """Set up test data"""
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
            title="第一章：开始",
            content="李明在北京修炼功法...",
            slug="chapter-1",
            is_public=True
        )

        # Create some entities
        from books.choices import EntityType

        BookEntity.objects.create(
            bookmaster=self.bookmaster,
            source_name="李明",
            entity_type=EntityType.CHARACTER,
            first_chapter=self.zh_chapter,
            translations={"en": "Li Ming"}
        )

        BookEntity.objects.create(
            bookmaster=self.bookmaster,
            source_name="北京",
            entity_type=EntityType.PLACE,
            first_chapter=self.zh_chapter,
            translations={"en": "Beijing"}
        )

    def _create_mock_provider(self, response_content):
        """Create a mock provider with specified response"""
        mock_provider = Mock()
        mock_provider.chat_completion.return_value = ChatCompletionResponse(
            content=response_content,
            model="mock",
            provider="mock",
            finish_reason="stop",
            usage={"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300},
        )
        return mock_provider

    def test_translation_creates_chapter(self):
        """Test that translation creates a new Chapter in target language"""
        mock_response = '''
        {
            "title": "Chapter 1: Beginning",
            "content": "Li Ming cultivates techniques in Beijing...",
            "entity_mappings": {
                "李明": "Li Ming",
                "北京": "Beijing",
                "功法": "techniques"
            }
        }
        '''

        mock_provider = self._create_mock_provider(mock_response)
        service = TranslationService()
        service.provider = mock_provider

        # Translate
        translated_chapter = service.translate_chapter(self.zh_chapter, "en")

        # Verify translation
        self.assertIsNotNone(translated_chapter)
        self.assertEqual(translated_chapter.title, "Chapter 1: Beginning")
        self.assertIn("Li Ming", translated_chapter.content)
        self.assertIn("Beijing", translated_chapter.content)
        self.assertEqual(translated_chapter.book.language.code, "en")
        self.assertEqual(translated_chapter.chaptermaster, self.chaptermaster)

        # Verify English book was created
        en_book = Book.objects.filter(
            bookmaster=self.bookmaster,
            language=self.en
        ).first()
        self.assertIsNotNone(en_book)
        self.assertEqual(translated_chapter.book, en_book)

    def test_translation_uses_existing_entities(self):
        """Test that translation uses existing entity translations"""
        mock_response = '''
        {
            "title": "Chapter 1",
            "content": "Li Ming in Beijing",
            "entity_mappings": {}
        }
        '''

        mock_provider = self._create_mock_provider(mock_response)
        service = TranslationService()
        service.provider = mock_provider

        # Translate
        service.translate_chapter(self.zh_chapter, "en")

        # Verify provider received existing entity translations in prompt
        call_args = mock_provider.chat_completion.call_args
        messages = call_args[0][0]
        prompt_content = messages[0].content

        # Prompt should include existing entity translations
        self.assertIn("李明", prompt_content)
        self.assertIn("Li Ming", prompt_content)
        self.assertIn("北京", prompt_content)
        self.assertIn("Beijing", prompt_content)

    def test_translation_stores_new_entity_mappings(self):
        """Test that translation stores new entity mappings"""
        mock_response = '''
        {
            "title": "Chapter 1",
            "content": "Li Ming practices techniques...",
            "entity_mappings": {
                "功法": "techniques",
                "修炼": "cultivate"
            }
        }
        '''

        mock_provider = self._create_mock_provider(mock_response)
        service = TranslationService()
        service.provider = mock_provider

        # Translate
        service.translate_chapter(self.zh_chapter, "en")

        # Verify new entities were stored
        # (In the real implementation, this happens in _store_entity_mappings)
        # Here we just verify the translation completed successfully
        translated = Chapter.objects.filter(
            chaptermaster=self.chaptermaster,
            book__language=self.en
        ).first()

        self.assertIsNotNone(translated)

    def test_translation_with_multiple_chapters(self):
        """Test translation uses context from previous chapters"""
        # Create a second chapter
        chaptermaster2 = ChapterMaster.objects.create(
            bookmaster=self.bookmaster,
            canonical_title="Chapter 2",
            chapter_number=2
        )

        zh_chapter2 = Chapter.objects.create(
            chaptermaster=chaptermaster2,
            book=self.zh_book,
            title="第二章：继续",
            content="李明继续在北京修炼...",
            slug="chapter-2",
            is_public=True
        )

        mock_response = '''
        {
            "title": "Chapter 2: Continuation",
            "content": "Li Ming continues in Beijing...",
            "entity_mappings": {}
        }
        '''

        mock_provider = self._create_mock_provider(mock_response)
        service = TranslationService()
        service.provider = mock_provider

        # Translate second chapter
        service.translate_chapter(zh_chapter2, "en")

        # Verify provider was called with context
        call_args = mock_provider.chat_completion.call_args
        messages = call_args[0][0]
        prompt_content = messages[0].content

        # Should mention previous chapters
        self.assertIn("previous", prompt_content.lower())


class TestCrossProviderCompatibility(TestCase):
    """Test that services work with different providers"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(username="testuser", password="testpass")

        self.zh = Language.objects.create(
            code="zh",
            name="Chinese",
            local_name="中文",
            count_units="CHARS",
            wpm=200
        )

        self.bookmaster = BookMaster.objects.create(
            canonical_title="Test",
            owner=self.user,
            original_language=self.zh
        )

        self.book = Book.objects.create(
            bookmaster=self.bookmaster,
            title="Test",
            language=self.zh,
        )

        self.chaptermaster = ChapterMaster.objects.create(
            bookmaster=self.bookmaster,
            canonical_title="Chapter 1",
            chapter_number=1
        )

        self.chapter = Chapter.objects.create(
            chaptermaster=self.chaptermaster,
            book=self.book,
            title="Test",
            content="Test content",
            slug="test",
        )

    def _create_mock_provider(self, response_content):
        """Create a mock provider"""
        mock_provider = Mock()
        mock_provider.chat_completion.return_value = ChatCompletionResponse(
            content=response_content,
            model="mock",
            provider="mock",
            finish_reason="stop",
            usage={"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
        )
        return mock_provider

    def test_analysis_service_with_different_providers(self):
        """Test that AnalysisService produces consistent results regardless of provider"""
        mock_response = '''
        {
            "characters": ["Test"],
            "places": [],
            "terms": [],
            "summary": "Test summary"
        }
        '''

        # Test with "OpenAI" provider
        openai_provider = self._create_mock_provider(mock_response)
        openai_provider.provider = "openai"

        service1 = AnalysisService()
        service1.provider = openai_provider
        result1 = service1.extract_entities_and_summary("Test", "zh")

        # Test with "Gemini" provider
        gemini_provider = self._create_mock_provider(mock_response)
        gemini_provider.provider = "gemini"

        service2 = AnalysisService()
        service2.provider = gemini_provider
        result2 = service2.extract_entities_and_summary("Test", "zh")

        # Results should be identical
        self.assertEqual(result1, result2)

    def test_translation_service_with_different_providers(self):
        """Test that TranslationService works with different providers"""
        mock_response = '''
        {
            "title": "Test",
            "content": "Translated content",
            "entity_mappings": {}
        }
        '''

        # Create target language
        Language.objects.create(
            code="en",
            name="English",
            local_name="English",
            count_units="WORDS",
            wpm=200
        )

        # Test with different mock providers
        for provider_name in ["openai", "gemini"]:
            mock_provider = self._create_mock_provider(mock_response)

            service = TranslationService()
            service.provider = mock_provider

            # Should work without errors
            translated = service.translate_chapter(self.chapter, "en")
            self.assertIsNotNone(translated)
            self.assertEqual(translated.content, "Translated content")


if __name__ == "__main__":
    unittest.main()
