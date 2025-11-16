"""
Test cases for hierarchical taxonomy system.

Tests cover:
- Model validation (Genre, BookMaster)
- Admin form validation
- Search functionality
- Integration workflows
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from books.models import Section, Genre, BookMaster, BookGenre, Tag, BookKeyword, Language


class GenreValidationTestCase(TestCase):
    """Test Genre model validation rules"""

    def setUp(self):
        self.section1 = Section.objects.create(name='Fiction', slug='fiction')
        self.section2 = Section.objects.create(name='BL', slug='bl')

    def test_primary_genre_cannot_have_parent(self):
        """Primary genres cannot have a parent"""
        parent = Genre.objects.create(
            name='Fantasy',
            section=self.section1,
            is_primary=True
        )

        genre = Genre(
            name='Epic Fantasy',
            section=self.section1,
            is_primary=True,  # Primary but trying to set parent
            parent=parent
        )

        with self.assertRaises(ValidationError) as cm:
            genre.clean()

        self.assertIn('parent', cm.exception.message_dict)

    def test_subgenre_must_have_parent(self):
        """Sub-genres must have a parent"""
        genre = Genre(
            name='Epic Fantasy',
            section=self.section1,
            is_primary=False,  # Sub-genre
            parent=None  # But no parent
        )

        with self.assertRaises(ValidationError) as cm:
            genre.clean()

        self.assertIn('parent', cm.exception.message_dict)

    def test_parent_must_be_same_section(self):
        """Parent genre must belong to same section"""
        parent = Genre.objects.create(
            name='Fantasy',
            section=self.section1,
            is_primary=True
        )

        genre = Genre(
            name='Epic Fantasy',
            section=self.section2,  # Different section
            is_primary=False,
            parent=parent
        )

        with self.assertRaises(ValidationError) as cm:
            genre.clean()

        self.assertIn('parent', cm.exception.message_dict)

    def test_genre_cannot_be_own_parent(self):
        """Genre cannot be its own parent"""
        genre = Genre.objects.create(
            name='Fantasy',
            section=self.section1,
            is_primary=True
        )

        genre.parent = genre

        with self.assertRaises(ValidationError) as cm:
            genre.clean()

        self.assertIn('parent', cm.exception.message_dict)

    def test_circular_reference_detection(self):
        """Detect circular parent references"""
        genre_a = Genre.objects.create(
            name='Fantasy',
            section=self.section1,
            is_primary=True
        )

        genre_b = Genre.objects.create(
            name='Epic Fantasy',
            section=self.section1,
            is_primary=False,
            parent=genre_a
        )

        # Try to create circular reference: A -> B -> A
        genre_a.parent = genre_b

        with self.assertRaises(ValidationError) as cm:
            genre_a.clean()

        self.assertIn('parent', cm.exception.message_dict)

    def test_valid_genre_hierarchy(self):
        """Valid genre hierarchy should pass validation"""
        parent = Genre.objects.create(
            name='Fantasy',
            section=self.section1,
            is_primary=True
        )

        subgenre = Genre(
            name='Epic Fantasy',
            section=self.section1,
            is_primary=False,
            parent=parent
        )

        # Should not raise
        subgenre.clean()
        subgenre.save()

        self.assertEqual(subgenre.parent, parent)


class BookMasterValidationTestCase(TestCase):
    """Test BookMaster model validation rules"""

    def setUp(self):
        self.section1 = Section.objects.create(name='Fiction', slug='fiction')
        self.section2 = Section.objects.create(name='BL', slug='bl')

        # Create language
        self.lang = Language.objects.create(
            code='en',
            name='English',
            count_units='words',
            wpm=250
        )

        self.genre1 = Genre.objects.create(
            name='Fantasy',
            section=self.section1,
            is_primary=True
        )
        self.genre2 = Genre.objects.create(
            name='Romance',
            section=self.section2,
            is_primary=True
        )

    def test_cannot_change_section_with_incompatible_genres(self):
        """Cannot change section when genres from old section exist"""
        bookmaster = BookMaster.objects.create(
            canonical_title='Test Book',
            section=self.section1,
            original_language=self.lang
        )

        # Add genre from section1
        BookGenre.objects.create(
            bookmaster=bookmaster,
            genre=self.genre1,
            order=1
        )

        # Try to change to section2
        bookmaster.section = self.section2

        with self.assertRaises(ValidationError) as cm:
            bookmaster.clean()

        self.assertIn('section', cm.exception.message_dict)

    def test_can_change_section_after_removing_genres(self):
        """Can change section after removing incompatible genres"""
        bookmaster = BookMaster.objects.create(
            canonical_title='Test Book',
            section=self.section1,
            original_language=self.lang
        )

        # Add genre from section1
        book_genre = BookGenre.objects.create(
            bookmaster=bookmaster,
            genre=self.genre1,
            order=1
        )

        # Remove genre
        book_genre.delete()

        # Should be able to change section now
        bookmaster.section = self.section2
        bookmaster.clean()  # Should not raise
        bookmaster.save()

        self.assertEqual(bookmaster.section, self.section2)

    def test_validate_genres_warns_no_genres(self):
        """validate_genres() warns when no genres assigned"""
        bookmaster = BookMaster.objects.create(
            canonical_title='Test Book',
            section=self.section1,
            original_language=self.lang
        )

        warnings = bookmaster.validate_genres()

        self.assertTrue(len(warnings) > 0)
        self.assertIn('no genres', warnings[0].lower())

    def test_validate_genres_warns_only_subgenres(self):
        """validate_genres() warns when only sub-genres assigned"""
        parent = Genre.objects.create(
            name='Mystery',
            slug='mystery',
            section=self.section1,
            is_primary=True
        )
        subgenre = Genre.objects.create(
            name='Detective',
            slug='detective',
            section=self.section1,
            is_primary=False,
            parent=parent
        )

        bookmaster = BookMaster.objects.create(
            canonical_title='Test Book',
            section=self.section1,
            original_language=self.lang
        )

        # Add only sub-genre
        BookGenre.objects.create(
            bookmaster=bookmaster,
            genre=subgenre,
            order=1
        )

        warnings = bookmaster.validate_genres()

        self.assertTrue(len(warnings) > 0)
        self.assertIn('primary', warnings[0].lower())

    def test_validate_genres_no_warnings_with_valid_setup(self):
        """validate_genres() returns no warnings for valid setup"""
        parent = Genre.objects.create(
            name='Horror',
            slug='horror',
            section=self.section1,
            is_primary=True
        )

        bookmaster = BookMaster.objects.create(
            canonical_title='Test Book',
            section=self.section1,
            original_language=self.lang
        )

        # Add primary genre
        BookGenre.objects.create(
            bookmaster=bookmaster,
            genre=parent,
            order=1
        )

        warnings = bookmaster.validate_genres()

        self.assertEqual(len(warnings), 0)


class SearchFunctionalityTestCase(TestCase):
    """Test search functionality"""

    def setUp(self):
        from books.models import Book

        self.zh_lang = Language.objects.create(
            code='zh',
            name='Chinese',
            count_units='chars',
            wpm=300
        )
        self.section = Section.objects.create(name='Fiction', slug='fiction')
        self.genre = Genre.objects.create(
            name='Fantasy',
            section=self.section,
            is_primary=True
        )

        self.bookmaster = BookMaster.objects.create(
            canonical_title='Test Fantasy Book',
            section=self.section,
            original_language=self.zh_lang
        )

        BookGenre.objects.create(
            bookmaster=self.bookmaster,
            genre=self.genre,
            order=1
        )

        # Create a Book instance (required for search)
        self.book = Book.objects.create(
            bookmaster=self.bookmaster,
            language=self.zh_lang,
            title='Test Fantasy Book',
            is_public=True,
            progress='ongoing'
        )

        # Create keyword
        BookKeyword.objects.create(
            bookmaster=self.bookmaster,
            keyword='fantasy',
            keyword_type='genre',
            language_code='zh',
            weight=1.0
        )

    def test_search_finds_book_by_keyword(self):
        """Search should find book by keyword"""
        from books.utils.search import BookSearchService

        result = BookSearchService.search(
            query='fantasy',
            language_code='zh'
        )

        self.assertGreater(result['total_results'], 0)
        self.assertIn('fantasy', result['matched_keywords'])

    def test_search_with_section_filter(self):
        """Search should respect section filter"""
        from books.utils.search import BookSearchService

        result = BookSearchService.search(
            query='fantasy',
            language_code='zh',
            section_slug='fiction'
        )

        self.assertGreater(result['total_results'], 0)

    def test_search_empty_query_returns_empty(self):
        """Search with empty query returns empty results"""
        from books.utils.search import BookSearchService

        result = BookSearchService.search(
            query='',
            language_code='zh'
        )

        self.assertEqual(result['total_results'], 0)
        self.assertEqual(len(result['books']), 0)


class TaxonomyIntegrationTestCase(TestCase):
    """Integration tests for complete taxonomy workflow"""

    def setUp(self):
        # Create complete taxonomy structure
        self.zh_lang = Language.objects.create(
            code='zh',
            name='Chinese',
            count_units='chars',
            wpm=300
        )
        self.section = Section.objects.create(name='Fiction', slug='fiction')

        self.primary_genre = Genre.objects.create(
            name='Fantasy',
            section=self.section,
            is_primary=True
        )

        self.sub_genre = Genre.objects.create(
            name='Epic Fantasy',
            section=self.section,
            is_primary=False,
            parent=self.primary_genre
        )

        self.tag = Tag.objects.create(
            name='Strong Protagonist',
            slug='strong-protagonist',
            category='protagonist'
        )

    def test_complete_bookmaster_setup(self):
        """Test complete BookMaster setup with genres and tags"""
        # Create BookMaster
        bookmaster = BookMaster.objects.create(
            canonical_title='Epic Fantasy Adventure',
            section=self.section,
            original_language=self.zh_lang
        )

        # Add primary genre
        BookGenre.objects.create(
            bookmaster=bookmaster,
            genre=self.primary_genre,
            order=1
        )

        # Add sub-genre
        BookGenre.objects.create(
            bookmaster=bookmaster,
            genre=self.sub_genre,
            order=2
        )

        # Add tag
        from books.models import BookTag
        BookTag.objects.create(
            bookmaster=bookmaster,
            tag=self.tag
        )

        # Verify setup
        self.assertEqual(bookmaster.book_genres.count(), 2)
        self.assertEqual(bookmaster.book_tags.count(), 1)

        # Validate genres
        warnings = bookmaster.validate_genres()
        self.assertEqual(len(warnings), 0)

    def test_section_change_workflow(self):
        """Test proper workflow for changing section"""
        # Create BookMaster with genre
        bookmaster = BookMaster.objects.create(
            canonical_title='Test Book',
            section=self.section,
            original_language=self.zh_lang
        )

        book_genre = BookGenre.objects.create(
            bookmaster=bookmaster,
            genre=self.primary_genre,
            order=1
        )

        # Create new section with genre
        new_section = Section.objects.create(name='BL', slug='bl')
        new_genre = Genre.objects.create(
            name='BL Fantasy',
            section=new_section,
            is_primary=True
        )

        # Step 1: Remove old genres
        book_genre.delete()

        # Step 2: Change section
        bookmaster.section = new_section
        bookmaster.save()

        # Step 3: Add new genres
        BookGenre.objects.create(
            bookmaster=bookmaster,
            genre=new_genre,
            order=1
        )

        # Verify
        self.assertEqual(bookmaster.section, new_section)
        self.assertEqual(bookmaster.book_genres.first().genre, new_genre)
