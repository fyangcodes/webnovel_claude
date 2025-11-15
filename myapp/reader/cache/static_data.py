"""
Static data caching for languages, genres, sections, and tags.

These are admin-managed taxonomies that rarely change, so we use long TTL
(1 hour) and invalidate via signals when models are saved/deleted.
"""

from django.core.cache import cache
from collections import defaultdict

from books.models import Language, Genre, Section, Tag
from . import TIMEOUT_STATIC


# ==============================================================================
# LANGUAGE CACHING
# ==============================================================================


def get_cached_languages(user=None):
    """
    Get languages from cache or database, filtered by visibility.

    Cache keys:
    - languages:public (for non-staff users)
    - languages:all (for staff users)

    TTL: 1 hour (rarely changes, admin-only)
    Invalidated by: Language model save/delete signals

    Args:
        user: Django User object or None. If staff, returns all languages.
              Otherwise, returns only public languages.

    Returns:
        list: Language objects ordered by code (de, en, fr, ja, zh)
    """
    # Determine if user is staff
    is_staff = user and user.is_authenticated and user.is_staff

    # Use different cache keys for staff vs non-staff
    cache_key = "languages:all" if is_staff else "languages:public"
    languages = cache.get(cache_key)

    if languages is None:
        if is_staff:
            # Staff sees all languages ordered by code (de, en, fr, ja, zh)
            languages = list(Language.objects.all().order_by("code"))
        else:
            # Non-staff sees only public languages ordered by code
            languages = list(
                Language.objects.filter(is_public=True).order_by("code")
            )

        cache.set(cache_key, languages, timeout=TIMEOUT_STATIC)

    return languages


# ==============================================================================
# SECTION CACHING
# ==============================================================================


def get_cached_sections(user=None):
    """
    Get sections from cache or database, filtered by maturity and visibility.

    Cache keys:
    - sections:all (for staff users)
    - sections:public (for non-staff users, may filter mature content in future)

    TTL: 1 hour (rarely changes, admin-only)
    Invalidated by: Section model save/delete signals

    Args:
        user: Django User object or None. If staff, returns all sections.
              Otherwise, may filter by maturity (future: add age verification).

    Returns:
        list: Section objects ordered by order, name
    """
    # Determine if user is staff
    is_staff = user and user.is_authenticated and user.is_staff

    # Use different cache keys for staff vs non-staff
    cache_key = "sections:all" if is_staff else "sections:public"
    sections = cache.get(cache_key)

    if sections is None:
        if is_staff:
            # Staff sees all sections
            sections = list(Section.objects.all().order_by("order", "name"))
        else:
            # Non-staff sees all sections for now
            # Future: filter by is_mature based on age verification
            sections = list(Section.objects.all().order_by("order", "name"))

        cache.set(cache_key, sections, timeout=TIMEOUT_STATIC)

    return sections


# ==============================================================================
# GENRE CACHING
# ==============================================================================


def get_cached_genres(section_id=None):
    """
    Get genres from cache or database with hierarchical structure grouped by section.

    Returns genres organized by section with parent-child relationships intact.
    This is optimized for navigation menus and browsing UIs that show section-genre
    hierarchies.

    Cache keys:
    - genres:hierarchical:all (all genres, all sections)
    - genres:hierarchical:section:{section_id} (genres for specific section)

    TTL: 1 hour (rarely changes, admin-only)
    Invalidated by: Genre model save/delete signals

    Args:
        section_id: Optional section ID to filter genres. If None, returns all.

    Returns:
        If section_id is None:
            dict: {
                section_id: {
                    'section': Section object,
                    'primary_genres': [Genre objects with is_primary=True],
                    'sub_genres': {
                        parent_genre_id: [Genre objects with parent=parent_id]
                    }
                }
            }
        If section_id is specified:
            dict: {
                'section': Section object,
                'primary_genres': [Genre objects],
                'sub_genres': {parent_genre_id: [Genre objects]}
            }
    """
    # Determine cache key
    if section_id is None:
        cache_key = "genres:hierarchical:all"
    else:
        cache_key = f"genres:hierarchical:section:{section_id}"

    result = cache.get(cache_key)

    if result is None:
        # Build query with optimized select_related
        queryset = (
            Genre.objects.select_related("section", "parent")
            .filter(section__isnull=False)
            .order_by("section__order", "section__name", "-is_primary", "name")
        )

        # Filter by section if specified
        if section_id is not None:
            queryset = queryset.filter(section_id=section_id)

        # Fetch all genres
        all_genres = list(queryset)

        if section_id is None:
            # Build hierarchical structure grouped by section
            result = {}
            for genre in all_genres:
                section = genre.section
                section_id_key = section.id

                # Initialize section entry if not exists
                if section_id_key not in result:
                    result[section_id_key] = {
                        "section": section,
                        "primary_genres": [],
                        "sub_genres": defaultdict(list),
                    }

                # Categorize genre
                if genre.is_primary:
                    result[section_id_key]["primary_genres"].append(genre)
                else:
                    # Add to parent's sub-genre list
                    if genre.parent:
                        result[section_id_key]["sub_genres"][genre.parent.id].append(
                            genre
                        )

        else:
            # Build structure for single section
            result = {
                "section": None,
                "primary_genres": [],
                "sub_genres": defaultdict(list),
            }

            for genre in all_genres:
                if result["section"] is None and genre.section:
                    result["section"] = genre.section

                if genre.is_primary:
                    result["primary_genres"].append(genre)
                else:
                    if genre.parent:
                        result["sub_genres"][genre.parent.id].append(genre)

            # Convert defaultdict to regular dict for caching
            result["sub_genres"] = dict(result["sub_genres"])

        # Convert defaultdicts to dicts for caching (if section_id is None)
        if section_id is None:
            for section_key in result:
                result[section_key]["sub_genres"] = dict(
                    result[section_key]["sub_genres"]
                )

        cache.set(cache_key, result, timeout=TIMEOUT_STATIC)

    return result


def get_cached_genres_flat(section_id=None):
    """
    Get flat list of genres from cache or database.

    This is a convenience function for backward compatibility and simple use cases
    where hierarchical structure is not needed. Use this when you just need to
    loop through genres without nesting.

    Cache keys:
    - genres:flat:all
    - genres:flat:section:{section_id}

    TTL: 1 hour
    Invalidated by: Genre model save/delete signals

    Args:
        section_id: Optional section ID to filter genres

    Returns:
        list: Genre objects ordered by section, is_primary (desc), name
    """
    # Determine cache key
    if section_id is None:
        cache_key = "genres:flat:all"
    else:
        cache_key = f"genres:flat:section:{section_id}"

    genres = cache.get(cache_key)

    if genres is None:
        # Build query
        queryset = (
            Genre.objects.select_related("section", "parent")
            .filter(section__isnull=False)
            .order_by("section__order", "section__name", "-is_primary", "name")
        )

        # Filter by section if specified
        if section_id is not None:
            queryset = queryset.filter(section_id=section_id)

        genres = list(queryset)
        cache.set(cache_key, genres, timeout=TIMEOUT_STATIC)

    return genres


def get_cached_featured_genres(featured_genre_ids):
    """
    Get featured genres from cache or database.

    Cache key: genres:featured
    TTL: 1 hour
    Invalidated by: Genre model save/delete signals

    Args:
        featured_genre_ids: List of genre IDs to fetch

    Returns:
        list: Featured Genre objects with section prefetched
    """
    if not featured_genre_ids:
        return []

    cache_key = "genres:featured"
    genres = cache.get(cache_key)

    if genres is None:
        genres = list(
            Genre.objects.filter(id__in=featured_genre_ids)
            .select_related("section", "parent")
            .order_by("section__order", "-is_primary", "name")
        )
        cache.set(cache_key, genres, timeout=TIMEOUT_STATIC)

    return genres


# ==============================================================================
# TAG CACHING
# ==============================================================================


def get_cached_tags(category=None):
    """
    Get tags from cache or database, optionally filtered by category.

    Cache keys:
    - tags:all (all tags grouped by category)
    - tags:category:{category} (specific category)

    TTL: 1 hour (rarely changes, admin-only)
    Invalidated by: Tag model save/delete signals

    Args:
        category: Optional TagCategory choice value to filter tags

    Returns:
        If category is None:
            dict: {category_value: [Tag objects]}
        If category is specified:
            list: [Tag objects for that category]
    """
    # Determine cache key
    if category is None:
        cache_key = "tags:all"
    else:
        cache_key = f"tags:category:{category}"

    result = cache.get(cache_key)

    if result is None:
        if category is None:
            # Get all tags and group by category
            all_tags = list(Tag.objects.all().order_by("category", "name"))

            result = defaultdict(list)
            for tag in all_tags:
                result[tag.category].append(tag)

            # Convert to regular dict for caching
            result = dict(result)
        else:
            # Get tags for specific category
            result = list(
                Tag.objects.filter(category=category).order_by("name")
            )

        cache.set(cache_key, result, timeout=TIMEOUT_STATIC)

    return result
