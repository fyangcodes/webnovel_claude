"""
Sitemap configuration for the reader app.

Provides sitemaps for:
- Section pages
- Book pages (section-scoped)
- Chapter pages (section-scoped)
- Static pages (welcome, search, etc.)
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from books.models import Book, Chapter, Section, Language


class SectionSitemap(Sitemap):
    """Sitemap for section landing pages"""

    changefreq = "daily"
    priority = 0.9

    def items(self):
        """Return all public sections for all public languages"""
        items = []
        sections = Section.objects.all()
        languages = Language.objects.filter(is_public=True)

        for language in languages:
            for section in sections:
                items.append({
                    'language_code': language.code,
                    'section_slug': section.slug,
                    'section': section
                })

        return items

    def location(self, item):
        """Return the URL for each section"""
        return reverse('reader:section_home', args=[
            item['language_code'],
            item['section_slug']
        ])

    def lastmod(self, item):
        """Return last modified date based on most recent book in section"""
        try:
            latest_book = Book.objects.filter(
                language__code=item['language_code'],
                bookmaster__section=item['section'],
                is_public=True
            ).order_by('-published_at', '-updated_at').first()

            return latest_book.updated_at if latest_book else None
        except Exception:
            return None


class BookSitemap(Sitemap):
    """Sitemap for book detail pages (section-scoped)"""

    changefreq = "weekly"
    priority = 0.8

    def items(self):
        """Return all public books"""
        return Book.objects.filter(
            is_public=True,
            bookmaster__section__isnull=False
        ).select_related(
            'language',
            'bookmaster__section'
        ).order_by('-published_at')

    def location(self, book):
        """Return section-scoped URL for book"""
        return reverse('reader:section_book_detail', args=[
            book.language.code,
            book.bookmaster.section.slug,
            book.slug
        ])

    def lastmod(self, book):
        """Return last modified date"""
        return book.updated_at


class ChapterSitemap(Sitemap):
    """Sitemap for chapter pages (section-scoped)"""

    changefreq = "monthly"
    priority = 0.6

    def items(self):
        """Return all public chapters"""
        return Chapter.objects.filter(
            is_public=True,
            book__is_public=True,
            book__bookmaster__section__isnull=False
        ).select_related(
            'book__language',
            'book__bookmaster__section',
            'book'
        ).order_by('-published_at')[:5000]  # Limit for performance

    def location(self, chapter):
        """Return section-scoped URL for chapter"""
        return reverse('reader:section_chapter_detail', args=[
            chapter.book.language.code,
            chapter.book.bookmaster.section.slug,
            chapter.book.slug,
            chapter.slug
        ])

    def lastmod(self, chapter):
        """Return last modified date"""
        return chapter.updated_at


class StaticViewSitemap(Sitemap):
    """Sitemap for static pages"""

    changefreq = "weekly"
    priority = 0.5

    def items(self):
        """Return language codes for static pages"""
        languages = Language.objects.filter(is_public=True)
        return [{
            'name': 'welcome',
            'language_code': lang.code
        } for lang in languages]

    def location(self, item):
        """Return URL for static page"""
        return reverse('reader:welcome', args=[item['language_code']])


# Sitemap dictionary for django.contrib.sitemaps
sitemaps = {
    'sections': SectionSitemap,
    'books': BookSitemap,
    'chapters': ChapterSitemap,
    'static': StaticViewSitemap,
}
