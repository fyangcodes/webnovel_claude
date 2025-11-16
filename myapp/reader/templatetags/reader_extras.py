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
        {% seo_meta_tags 'book' book=book language=current_language %}
        {% seo_meta_tags 'section' section=section language=current_language %}
        {% seo_meta_tags 'chapter' chapter=chapter book=book language=current_language %}

    Args:
        page_type: Type of page ('book', 'section', 'chapter', 'home')
        **kwargs: Page-specific data (book, section, chapter, etc.)

    Returns:
        HTML meta tags as safe string
    """
    tags = []

    if page_type == 'book':
        book = kwargs.get('book')
        language = kwargs.get('language')
        if book:
            title = f"{book.title} - {language.local_name if language else ''}"
            description = book.description[:160] if book.description else f"Read {book.title} online"
            image = book.effective_cover_image if book.effective_cover_image else ''

            tags.append(f'<meta name="description" content="{description}">')
            tags.append(f'<meta name="keywords" content="{book.author}, webnovel, {book.title}">')

            # Open Graph
            tags.append(f'<meta property="og:type" content="book">')
            tags.append(f'<meta property="og:title" content="{title}">')
            tags.append(f'<meta property="og:description" content="{description}">')
            if image:
                tags.append(f'<meta property="og:image" content="{image}">')
            tags.append(f'<meta property="book:author" content="{book.author}">')

            # Twitter Card
            tags.append(f'<meta name="twitter:card" content="summary_large_image">')
            tags.append(f'<meta name="twitter:title" content="{title}">')
            tags.append(f'<meta name="twitter:description" content="{description}">')
            if image:
                tags.append(f'<meta name="twitter:image" content="{image}">')

    elif page_type == 'section':
        section = kwargs.get('section')
        language = kwargs.get('language')
        if section:
            title = f"{section.get_localized_name(language.code)} - {language.local_name}"
            description = section.description or f"Browse {section.get_localized_name(language.code)} books"

            tags.append(f'<meta name="description" content="{description}">')
            tags.append(f'<meta property="og:type" content="website">')
            tags.append(f'<meta property="og:title" content="{title}">')
            tags.append(f'<meta property="og:description" content="{description}">')

    elif page_type == 'chapter':
        chapter = kwargs.get('chapter')
        book = kwargs.get('book')
        language = kwargs.get('language')
        if chapter and book:
            title = f"{chapter.title} - {book.title}"
            description = chapter.excerpt or f"Read {chapter.title} from {book.title}"

            tags.append(f'<meta name="description" content="{description}">')
            tags.append(f'<meta property="og:type" content="article">')
            tags.append(f'<meta property="og:title" content="{title}">')
            tags.append(f'<meta property="og:description" content="{description}">')
            tags.append(f'<meta property="article:author" content="{book.author}">')

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
