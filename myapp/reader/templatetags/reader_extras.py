"""
Custom template filters and tags for the reader app.

This module provides template utilities for working with hierarchical
taxonomy data structures (sections, genres, tags), and section-aware URL helpers.
"""

from django import template
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
import json

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary by key.
    
    Usage in templates:
        {{ my_dict|get_item:key_variable }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def get_sub_genres(sub_genres_dict, parent_id):
    """
    Get sub-genres for a parent genre from the hierarchical structure.
    
    Usage in templates:
        {% for sub_genre in section_data.sub_genres|get_sub_genres:parent_genre.id %}
    """
    if sub_genres_dict is None:
        return []
    return sub_genres_dict.get(parent_id, [])


@register.simple_tag
def query_transform(request, **kwargs):
    """
    Transform the current query string by adding/updating parameters.

    Usage in templates:
        <a href="?{% query_transform request section='bl' page=None %}">

    Use key=None to remove a parameter.
    """
    updated = request.GET.copy()
    for key, value in kwargs.items():
        if value is None:
            updated.pop(key, None)  # Remove parameter
        else:
            updated[key] = value
    return updated.urlencode()


# ============================================================================
# SECTION-AWARE URL HELPERS (Phase 3)
# ============================================================================
# These template tags make it easier to work with section URLs in templates


@register.simple_tag
def book_url(language_code, book):
    """
    Generate the correct URL for a book (section-aware).

    Usage in templates:
        <a href="{% book_url current_language.code book %}">{{ book.title }}</a>

    Returns section URL if book has section, otherwise legacy URL.
    """
    if hasattr(book, 'bookmaster') and book.bookmaster.section:
        return reverse(
            'reader:section_book_detail',
            args=[language_code, book.bookmaster.section.slug, book.slug]
        )
    else:
        return reverse('reader:book_detail', args=[language_code, book.slug])


@register.simple_tag
def chapter_url(language_code, chapter):
    """
    Generate the correct URL for a chapter (section-aware).

    Usage in templates:
        <a href="{% chapter_url current_language.code chapter %}">{{ chapter.title }}</a>

    Returns section URL if book has section, otherwise legacy URL.
    """
    book = chapter.book
    if hasattr(book, 'bookmaster') and book.bookmaster.section:
        return reverse(
            'reader:section_chapter_detail',
            args=[language_code, book.bookmaster.section.slug, book.slug, chapter.slug]
        )
    else:
        return reverse(
            'reader:chapter_detail',
            args=[language_code, book.slug, chapter.slug]
        )


@register.simple_tag
def section_book_list_url(language_code, section):
    """
    Generate URL for section book list.

    Usage in templates:
        <a href="{% section_book_list_url current_language.code section %}">Books</a>
    """
    return reverse('reader:section_book_list', args=[language_code, section.slug])


@register.simple_tag
def section_home_url(language_code, section):
    """
    Generate URL for section home page.

    Usage in templates:
        <a href="{% section_home_url current_language.code section %}">{{ section.name }}</a>
    """
    return reverse('reader:section_home', args=[language_code, section.slug])


@register.simple_tag
def genre_url(language_code, genre, section=None):
    """
    Generate the correct URL for a genre (section-aware if section provided).

    Usage in templates:
        <a href="{% genre_url current_language.code genre %}">{{ genre.name }}</a>
        <a href="{% genre_url current_language.code genre section %}">{{ genre.name }}</a>

    Returns section-scoped URL if section is provided, otherwise legacy URL.
    """
    if section:
        return reverse(
            'reader:section_genre_book_list',
            args=[language_code, section.slug, genre.slug]
        )
    else:
        return reverse('reader:genre_book_list', args=[language_code, genre.slug])


@register.simple_tag
def tag_url(language_code, tag, section=None):
    """
    Generate the correct URL for a tag (section-aware if section provided).

    Usage in templates:
        <a href="{% tag_url current_language.code tag %}">{{ tag.name }}</a>
        <a href="{% tag_url current_language.code tag section %}">{{ tag.name }}</a>

    Returns section-scoped URL if section is provided, otherwise legacy URL.
    """
    if section:
        return reverse(
            'reader:section_tag_book_list',
            args=[language_code, section.slug, tag.slug]
        )
    else:
        return reverse('reader:tag_book_list', args=[language_code, tag.slug])


@register.simple_tag
def search_url(language_code, section=None):
    """
    Generate the correct search URL (section-aware if section provided).

    Usage in templates:
        <form method="get" action="{% search_url current_language.code %}">
        <form method="get" action="{% search_url current_language.code section %}">

    Returns section search URL if section provided, otherwise global search.
    """
    if section:
        return reverse('reader:section_search', args=[language_code, section.slug])
    else:
        return reverse('reader:search', args=[language_code])


@register.filter
def has_section(book):
    """
    Check if a book has a section.

    Usage in templates:
        {% if book|has_section %}
            ...
        {% endif %}
    """
    return hasattr(book, 'bookmaster') and book.bookmaster.section is not None


@register.simple_tag(takes_context=True)
def current_section(context):
    """
    Get the current section from the context.

    Usage in templates:
        {% current_section as section %}
        {% if section %}
            <h1>{{ section.name }}</h1>
        {% endif %}

    Returns the section object if available, otherwise None.
    """
    return context.get('section', None)


# ============================================================================
# SEO Meta Tags and Structured Data
# ============================================================================

@register.simple_tag
def seo_meta_tags(page_type, **kwargs):
    """
    Generate SEO meta tags for different page types.

    Usage:
        {% seo_meta_tags 'book' book=book language=current_language request=request %}
        {% seo_meta_tags 'section' section=section language=current_language request=request %}
        {% seo_meta_tags 'chapter' chapter=chapter book=book language=current_language request=request %}

    Args:
        page_type: Type of page ('book', 'section', 'chapter', 'home')
        **kwargs: Page-specific data (book, section, chapter, etc.)

    Returns:
        HTML meta tags as safe string
    """
    from django.utils.html import escape

    tags = []
    request = kwargs.get('request')

    if page_type == 'book':
        book = kwargs.get('book')
        language = kwargs.get('language')
        if book:
            title = escape(f"{book.title} - {language.local_name if language else ''}")

            # Book description is already language-specific (Book is per-language)
            # No need for localization since each Book instance is in a specific language
            description = escape(book.description[:160] if book.description else f"Read {book.title} online")

            image = book.effective_cover_image if book.effective_cover_image else ''

            tags.append(f'<meta name="description" content="{description}">')

            # Build keywords (check if author exists)
            author_name = book.bookmaster.author.get_localized_name(language.code) if book.bookmaster.author else ""
            keywords = f"{escape(author_name)}, webnovel, {escape(book.title)}" if author_name else f"webnovel, {escape(book.title)}"
            tags.append(f'<meta name="keywords" content="{keywords}">')

            # Open Graph
            tags.append(f'<meta property="og:type" content="book">')
            tags.append(f'<meta property="og:title" content="{title}">')
            tags.append(f'<meta property="og:description" content="{description}">')
            if image:
                tags.append(f'<meta property="og:image" content="{escape(image)}">')
            if request:
                tags.append(f'<meta property="og:url" content="{escape(request.build_absolute_uri())}">')
            if language:
                tags.append(f'<meta property="og:locale" content="{escape(language.code)}">')
            tags.append(f'<meta property="book:author" content="{escape(book.author)}">')

            # Twitter Card
            tags.append(f'<meta name="twitter:card" content="summary_large_image">')
            tags.append(f'<meta name="twitter:title" content="{title}">')
            tags.append(f'<meta name="twitter:description" content="{description}">')
            if image:
                tags.append(f'<meta name="twitter:image" content="{escape(image)}">')

    elif page_type == 'section':
        section = kwargs.get('section')
        language = kwargs.get('language')
        if section:
            title = escape(f"{section.get_localized_name(language.code)} - {language.local_name}")

            # Use localized description
            localized_desc = section.get_localized_description(language.code) if language else section.description
            description = escape(localized_desc or f"Browse {section.get_localized_name(language.code)} books")

            tags.append(f'<meta name="description" content="{description}">')
            tags.append(f'<meta property="og:type" content="website">')
            tags.append(f'<meta property="og:title" content="{title}">')
            tags.append(f'<meta property="og:description" content="{description}">')
            if request:
                tags.append(f'<meta property="og:url" content="{escape(request.build_absolute_uri())}">')
            if language:
                tags.append(f'<meta property="og:locale" content="{escape(language.code)}">')

    elif page_type == 'chapter':
        chapter = kwargs.get('chapter')
        book = kwargs.get('book')
        language = kwargs.get('language')
        if chapter and book:
            title = escape(f"{chapter.title} - {book.title}")

            # Chapter excerpt is already language-specific (Chapter is per-language)
            # No need for localization since each Chapter instance is in a specific language
            description = escape(chapter.excerpt or f"Read {chapter.title} from {book.title}")

            tags.append(f'<meta name="description" content="{description}">')
            tags.append(f'<meta property="og:type" content="article">')
            tags.append(f'<meta property="og:title" content="{title}">')
            tags.append(f'<meta property="og:description" content="{description}">')
            if request:
                tags.append(f'<meta property="og:url" content="{escape(request.build_absolute_uri())}">')
            if language:
                tags.append(f'<meta property="og:locale" content="{escape(language.code)}">')
            tags.append(f'<meta property="article:author" content="{escape(book.author)}">')

    return mark_safe('\n'.join(tags))


@register.simple_tag
def structured_data(data_type, **kwargs):
    """
    Generate JSON-LD structured data for SEO.

    Usage:
        {% structured_data 'book' book=book url=request.build_absolute_uri %}
        {% structured_data 'breadcrumb' items=breadcrumb_items %}

    Args:
        data_type: Type of structured data ('book', 'breadcrumb', 'organization')
        **kwargs: Data-specific arguments

    Returns:
        JSON-LD script tag as safe string
    """
    schema = None

    if data_type == 'book':
        book = kwargs.get('book')
        url = kwargs.get('url')
        if book:
            schema = {
                "@context": "https://schema.org",
                "@type": "Book",
                "name": book.title,
                "author": {
                    "@type": "Person",
                    "name": book.author
                },
                "inLanguage": book.language.code,
                "description": book.description or '',
                "numberOfPages": book.total_chapters,
                "url": url
            }

            if book.effective_cover_image:
                schema["image"] = book.effective_cover_image

            if book.published_at:
                schema["datePublished"] = book.published_at.isoformat()

    elif data_type == 'breadcrumb':
        items = kwargs.get('items', [])
        if items:
            item_list = []
            for i, item in enumerate(items, 1):
                item_list.append({
                    "@type": "ListItem",
                    "position": i,
                    "name": item.get('name', ''),
                    "item": item.get('url', '')
                })

            schema = {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": item_list
            }

    elif data_type == 'article':
        chapter = kwargs.get('chapter')
        book = kwargs.get('book')
        url = kwargs.get('url')
        if chapter and book:
            schema = {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": chapter.title,
                "author": {
                    "@type": "Person",
                    "name": book.author
                },
                "publisher": {
                    "@type": "Organization",
                    "name": "wereadly"
                },
                "inLanguage": book.language.code if hasattr(book, 'language') else 'en',
                "url": url
            }

            if chapter.published_at:
                schema["datePublished"] = chapter.published_at.isoformat()

            if chapter.updated_at:
                schema["dateModified"] = chapter.updated_at.isoformat()

            if hasattr(chapter, 'word_count') and chapter.word_count:
                schema["wordCount"] = chapter.word_count

            if chapter.excerpt:
                schema["description"] = chapter.excerpt

            # Link to parent book
            schema["isPartOf"] = {
                "@type": "Book",
                "name": book.title
            }

    elif data_type == 'website':
        site_name = kwargs.get('site_name', 'wereadly')
        url = kwargs.get('url')
        search_url = kwargs.get('search_url')

        schema = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": site_name,
            "url": url
        }

        if search_url:
            schema["potentialAction"] = {
                "@type": "SearchAction",
                "target": {
                    "@type": "EntryPoint",
                    "urlTemplate": search_url
                },
                "query-input": "required name=search_term_string"
            }

    elif data_type == 'organization':
        site_name = kwargs.get('site_name', 'wereadly')
        url = kwargs.get('url')
        schema = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": site_name,
            "url": url
        }

    if schema:
        json_output = json.dumps(schema, ensure_ascii=False, indent=2)
        return mark_safe(f'<script type="application/ld+json">\n{json_output}\n</script>')

    return ''


@register.simple_tag
def canonical_url(request):
    """
    Generate canonical URL for the current page.

    Usage:
        <link rel="canonical" href="{% canonical_url request %}">

    Args:
        request: Django request object

    Returns:
        Absolute URL for the current page
    """
    return request.build_absolute_uri(request.path)


@register.simple_tag(takes_context=True)
def hreflang_tags(context):
    """
    Generate hreflang tags for all available languages.

    This tag is context-aware and generates correct URLs based on the page type:
    - For book pages: Uses BookMaster to get slugs for each language
    - For chapter pages: Uses ChapterMaster to get slugs for each language
    - For other pages: Simple language code replacement in URL

    Usage in templates:
        {% hreflang_tags %}

    Returns:
        HTML link tags with hreflang attributes as safe string
    """
    from django.urls import reverse
    from books.models import Book, Chapter

    request = context.get('request')
    languages = context.get('languages')
    current_language = context.get('current_language')

    if not request or not languages or not current_language:
        return ''

    tags = []
    view_name = request.resolver_match.url_name if request.resolver_match else None

    # Get public languages only
    public_languages = [lang for lang in languages if lang.is_public or (hasattr(request, 'user') and request.user.is_staff)]

    # Handle book detail pages
    if view_name in ('book_detail', 'section_book_detail'):
        book = context.get('book')
        if book and hasattr(book, 'bookmaster'):
            bookmaster = book.bookmaster
            section_slug = bookmaster.section.slug

            # OPTIMIZATION: Use prefetched hreflang_books from context (0 queries)
            # Falls back to querying if context data not available (backwards compatible)
            hreflang_books = context.get('hreflang_books')

            if hreflang_books is not None:
                # Use prefetched data from view context (OPTIMIZED)
                related_books = hreflang_books
            else:
                # Fallback: Query database (backwards compatible for views that don't prefetch)
                related_books = Book.objects.filter(
                    bookmaster=bookmaster,
                    language__in=public_languages,
                    is_public=True
                ).select_related('language')

            # Create a mapping of language_code -> book_slug
            book_slugs = {b.language.code: b.slug for b in related_books}

            for lang in public_languages:
                if lang.code in book_slugs:
                    url = reverse('reader:section_book_detail', kwargs={
                        'language_code': lang.code,
                        'section_slug': section_slug,
                        'book_slug': book_slugs[lang.code]
                    })
                    absolute_url = request.build_absolute_uri(url)
                    tags.append(f'<link rel="alternate" hreflang="{lang.code}" href="{absolute_url}">')

            # Add x-default for English if available
            if 'en' in book_slugs:
                url = reverse('reader:section_book_detail', kwargs={
                    'language_code': 'en',
                    'section_slug': section_slug,
                    'book_slug': book_slugs['en']
                })
                absolute_url = request.build_absolute_uri(url)
                tags.append(f'<link rel="alternate" hreflang="x-default" href="{absolute_url}">')

    # Handle chapter detail pages
    elif view_name in ('chapter_detail', 'section_chapter_detail'):
        chapter = context.get('chapter')
        book = context.get('book')

        if chapter and book and hasattr(chapter, 'chaptermaster') and hasattr(book, 'bookmaster'):
            chaptermaster = chapter.chaptermaster
            bookmaster = book.bookmaster
            section_slug = bookmaster.section.slug

            # Get all chapters for this ChapterMaster in different languages
            related_chapters = Chapter.objects.filter(
                chaptermaster=chaptermaster,
                book__language__in=public_languages,
                is_public=True
            ).select_related('book', 'book__language')

            # Create a mapping of language_code -> (book_slug, chapter_slug)
            chapter_data = {
                c.book.language.code: (c.book.slug, c.slug)
                for c in related_chapters
            }

            for lang in public_languages:
                if lang.code in chapter_data:
                    book_slug, chapter_slug = chapter_data[lang.code]
                    url = reverse('reader:section_chapter_detail', kwargs={
                        'language_code': lang.code,
                        'section_slug': section_slug,
                        'book_slug': book_slug,
                        'chapter_slug': chapter_slug
                    })
                    absolute_url = request.build_absolute_uri(url)
                    tags.append(f'<link rel="alternate" hreflang="{lang.code}" href="{absolute_url}">')

            # Add x-default for English if available
            if 'en' in chapter_data:
                book_slug, chapter_slug = chapter_data['en']
                url = reverse('reader:section_chapter_detail', kwargs={
                    'language_code': 'en',
                    'section_slug': section_slug,
                    'book_slug': book_slug,
                    'chapter_slug': chapter_slug
                })
                absolute_url = request.build_absolute_uri(url)
                tags.append(f'<link rel="alternate" hreflang="x-default" href="{absolute_url}">')

    # Handle all other pages (section home, search, etc.) - simple language code replacement
    else:
        current_path = request.path
        language_code_pattern = request.resolver_match.kwargs.get('language_code') if request.resolver_match else None

        for lang in public_languages:
            if language_code_pattern:
                alternate_path = current_path.replace(f'/{language_code_pattern}/', f'/{lang.code}/', 1)
            else:
                alternate_path = f'/{lang.code}{current_path}'

            absolute_url = request.build_absolute_uri(alternate_path)
            tags.append(f'<link rel="alternate" hreflang="{lang.code}" href="{absolute_url}">')

        # Add x-default for English
        if language_code_pattern:
            default_path = current_path.replace(f'/{language_code_pattern}/', '/en/', 1)
        else:
            default_path = f'/en{current_path}'

        default_url = request.build_absolute_uri(default_path)
        tags.append(f'<link rel="alternate" hreflang="x-default" href="{default_url}">')

    return mark_safe('\n'.join(tags))


@register.filter
def localized_name(obj, language_code):
    """
    Get localized name for objects with LocalizationModel.

    Usage in templates:
        {{ author|localized_name:current_language.code }}
        {{ genre|localized_name:"zh-hans" }}

    Args:
        obj: Object with get_localized_name method (Author, Section, Genre, Tag, etc.)
        language_code: Language code string

    Returns:
        Localized name or original name as fallback
    """
    if obj is None:
        return ""
    if hasattr(obj, 'get_localized_name'):
        return obj.get_localized_name(language_code)
    # Fallback to name attribute if method doesn't exist
    return getattr(obj, 'name', str(obj))


@register.simple_tag
def enrich_book_meta(book):
    """
    Enrich book object with additional metadata like new chapters count.

    OPTIMIZED: Uses pre-calculated new_chapters_count from view enrichment.
    Falls back to database query only if not pre-calculated (backwards compatible).

    Usage in templates:
        {% enrich_book_meta book as book_meta %}
        {% if book_meta.new_chapters_count > 0 %}
            <span class="badge bg-danger">{{ book_meta.new_chapters_count }}</span>
        {% endif %}

    Args:
        book: Book object (should have new_chapters_count attribute from view)

    Returns:
        Dictionary with enriched metadata
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.conf import settings

    new_chapter_days = getattr(settings, 'NEW_CHAPTER_DAYS', 14)
    cutoff_date = timezone.now() - timedelta(days=new_chapter_days)

    # Try to use pre-calculated value from view enrichment
    if hasattr(book, 'new_chapters_count'):
        new_chapters_count = book.new_chapters_count
    else:
        # Fallback: Query database (backwards compatible)
        # This ensures the tag still works if enrichment wasn't done in view
        new_chapters_count = book.chapters.filter(
            is_public=True,
            published_at__gte=cutoff_date
        ).count()

    return {
        'book': book,
        'new_chapters_count': new_chapters_count,
        'new_chapter_cutoff': cutoff_date,
    }
