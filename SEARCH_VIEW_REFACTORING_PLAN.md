# Search View Refactoring Plan

## Overview

Unify `BookSearchView` and `SectionSearchView` while keeping their distinct concerns:
- **BookSearchView**: Global search across all sections
- **SectionSearchView**: Section-scoped search (keywords within specific section)

## Current State

### BookSearchView (`reader/views/list_views.py`)
- URL: `/<lang>/search/?q=<query>&section=<slug>&genre=<slug>`
- Section: Optional filter via query parameter
- Context: Minimal (selected filters only)

### SectionSearchView (`reader/views/section_views.py`)
- URL: `/<lang>/<section>/search/?q=<query>&genre=<slug>`
- Section: Required from URL path
- Context: Full genre hierarchy, section nav, localized names

### Duplicated Code (~60 lines)
- `get_queryset()`: Nearly identical search service call and order preservation
- Filter extraction (genre, tag, status)
- Search metadata context (matched_keywords, search_time_ms, total_results)

## Proposed Architecture

```
BaseSearchView (new)
├── BookSearchView (global search)
└── SectionSearchView (section-scoped search)
```

## Implementation Steps

### Step 1: Create BaseSearchView in `reader/views/base.py`

```python
class BaseSearchView(BaseBookListView):
    """
    Base class for search views with shared search logic.

    Subclasses must implement:
    - get_section_for_search(): Return Section or None
    """
    template_name = "reader/search.html"
    model = Book
    paginate_by = 20

    def get_section_for_search(self):
        """
        Return Section instance for scoping search, or None for global search.
        Subclasses override this method.
        """
        raise NotImplementedError

    def get_queryset(self):
        """Common search queryset logic."""
        query = self.request.GET.get('q', '').strip()

        if not query:
            self.search_results = None
            return Book.objects.none()

        # Get filter parameters
        genre_slug = self.request.GET.get('genre')
        tag_slug = self.request.GET.get('tag')
        status = self.request.GET.get('status')

        # Get section (implementation-specific)
        section = self.get_section_for_search()
        section_slug = section.slug if section else None

        # Get language
        language = self.get_language()

        # Perform search
        search_results = BookSearchService.search(
            query=query,
            language_code=language.code,
            section_slug=section_slug,
            genre_slug=genre_slug,
            tag_slug=tag_slug,
            status=status,
            limit=500
        )

        self.search_results = search_results

        book_ids = [book.id for book in search_results['books']]

        if not book_ids:
            return Book.objects.none()

        queryset = Book.objects.filter(id__in=book_ids).select_related(
            "bookmaster", "bookmaster__section", "language"
        ).prefetch_related(
            "chapters", "bookmaster__genres", "bookmaster__genres__section", "bookmaster__tags"
        )

        # Preserve search ranking order
        preserved_order = Case(*[When(id=pk, then=pos) for pos, pk in enumerate(book_ids)])
        return queryset.order_by(preserved_order)

    def get_search_context(self):
        """Return common search context data."""
        context = {}
        context['search_query'] = self.request.GET.get('q', '').strip()

        if hasattr(self, 'search_results') and self.search_results:
            context['matched_keywords'] = self.search_results['matched_keywords']
            context['search_time_ms'] = self.search_results['search_time_ms']
            context['total_results'] = self.search_results['total_results']
        else:
            context['matched_keywords'] = []
            context['search_time_ms'] = 0
            context['total_results'] = 0

        # Common filter values
        context["selected_genre"] = self.request.GET.get("genre", "")
        context["selected_tag"] = self.request.GET.get("tag", "")
        context["selected_status"] = self.request.GET.get("status", "")

        return context
```

### Step 2: Refactor BookSearchView (`reader/views/list_views.py`)

```python
class BookSearchView(BaseSearchView):
    """
    Global keyword search across all sections.

    URL: /<language_code>/search/?q=<query>&section=<slug>&genre=<slug>...
    """

    def get_section_for_search(self):
        """Get section from query parameter (optional filter)."""
        section_slug = self.request.GET.get('section')
        if section_slug:
            return Section.objects.filter(slug=section_slug).first()
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_search_context())

        # Global search specific: section as optional filter
        context["selected_section"] = self.request.GET.get("section", "")

        return context
```

### Step 3: Refactor SectionSearchView (`reader/views/section_views.py`)

```python
class SectionSearchView(BaseSearchView):
    """
    Search within a specific section.

    URL: /<language>/<section>/search/?q=<query>&genre=<slug>&tag=<slug>...
    """

    def get_section_for_search(self):
        """Get section from URL path (required)."""
        section = self.get_section()
        if not section:
            raise Http404("Section required")
        return section

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_search_context())

        section = self.get_section_for_search()
        language_code = self.kwargs.get("language_code")

        # Section-scoped specific context
        context['show_section_nav'] = True
        context["section"] = section
        context["section_localized_name"] = section.get_localized_name(language_code)

        # Genre hierarchy (existing logic)
        self._add_genre_hierarchy_context(context, section, language_code)

        return context

    def _add_genre_hierarchy_context(self, context, section, language_code):
        """Add full genre hierarchy for section-scoped search."""
        # ... existing genre hierarchy logic from current SectionSearchView
```

## Files to Modify

1. **`reader/views/base.py`** - Add `BaseSearchView` class
2. **`reader/views/list_views.py`** - Simplify `BookSearchView` to extend `BaseSearchView`
3. **`reader/views/section_views.py`** - Simplify `SectionSearchView` to extend `BaseSearchView`

## Benefits

1. **DRY**: ~60 lines of duplicated code eliminated
2. **Maintainability**: Search logic changes in one place
3. **Separation of concerns**: Each view maintains its distinct purpose
4. **Extensibility**: Easy to add new search variants (e.g., author search)

## Part 2: Add Title and Author Keywords

### Problem

Currently, `BookKeyword` only indexes:
- Section names (weight: 1.5)
- Genre names (weight: 1.0)
- Tag names (weight: 0.8)
- Entity names (weight: 0.6)

**Missing**: Book titles and author names are not searchable via keywords.

### Solution

Add two new keyword types and extraction functions to index book titles and authors.

### Step 1: Add KeywordType choices (`books/choices.py`)

```python
class KeywordType(models.TextChoices):
    """Types of keywords for search indexing"""
    SECTION = "section", "Section"
    GENRE = "genre", "Genre"
    TAG = "tag", "Tag"
    ENTITY_CHARACTER = "entity_character", "Character"
    ENTITY_PLACE = "entity_place", "Place"
    ENTITY_TERM = "entity_term", "Term"
    # NEW
    TITLE = "title", "Title"
    AUTHOR = "author", "Author"
```

### Step 2: Add extraction functions (`books/utils/keywords.py`)

```python
def _extract_title_keywords(bookmaster, seen_keywords: Set) -> List[BookKeyword]:
    """
    Extract keywords from book titles.

    Sources:
    - BookMaster.canonical_title (original language)
    - Book.title for each language version

    Weight: 2.0 (highest - direct title match is most relevant)
    """
    keywords = []
    weight = 2.0

    # Get original language code
    original_lang = bookmaster.original_language.code if bookmaster.original_language else 'zh'

    # Add canonical title (original language)
    _add_keyword(
        keywords, seen_keywords, bookmaster,
        bookmaster.canonical_title, KeywordType.TITLE, original_lang, weight
    )

    # Add titles from all language-specific Book instances
    for book in bookmaster.books.all():
        if book.title:
            _add_keyword(
                keywords, seen_keywords, bookmaster,
                book.title, KeywordType.TITLE, book.language.code, weight
            )

    return keywords


def _extract_author_keywords(bookmaster, seen_keywords: Set) -> List[BookKeyword]:
    """
    Extract keywords from author names.

    Sources:
    - Book.author for each language version

    Weight: 1.8 (high - author search is common use case)
    """
    keywords = []
    weight = 1.8

    # Get author names from all language-specific Book instances
    for book in bookmaster.books.all():
        if book.author:
            _add_keyword(
                keywords, seen_keywords, bookmaster,
                book.author, KeywordType.AUTHOR, book.language.code, weight
            )

    return keywords
```

### Step 3: Update `update_book_keywords()` function

```python
def update_book_keywords(bookmaster):
    """
    Rebuild all keywords for a bookmaster from taxonomy, entities, and book metadata.

    Keywords extracted from:
    - Book titles (weight: 2.0) - NEW
    - Author names (weight: 1.8) - NEW
    - Section name (weight: 1.5)
    - Genre names (weight: 1.0)
    - Tag names (weight: 0.8)
    - Entity names (weight: 0.6)
    """
    # Delete existing keywords
    BookKeyword.objects.filter(bookmaster=bookmaster).delete()

    keywords_to_create = []
    seen_keywords = set()

    # 1. Extract title keywords (NEW - highest weight)
    keywords_to_create.extend(
        _extract_title_keywords(bookmaster, seen_keywords)
    )

    # 2. Extract author keywords (NEW - high weight)
    keywords_to_create.extend(
        _extract_author_keywords(bookmaster, seen_keywords)
    )

    # 3. Extract section keywords
    if bookmaster.section:
        keywords_to_create.extend(
            _extract_section_keywords(bookmaster, seen_keywords)
        )

    # 4-6. Extract genre, tag, entity keywords (unchanged)
    # ...
```

### Step 4: Update signals to trigger keyword rebuild

Keywords should be rebuilt when:
- `Book.title` changes
- `Book.author` changes
- New `Book` is created for a `BookMaster`

Update `books/signals/keywords.py`:

```python
@receiver(post_save, sender=Book)
def update_keywords_on_book_save(sender, instance, **kwargs):
    """Rebuild keywords when Book title/author changes."""
    if instance.bookmaster:
        update_book_keywords(instance.bookmaster)
```

### Step 5: Migration to populate existing keywords

Create management command or data migration to rebuild keywords for all existing books:

```bash
python manage.py populate_book_keywords --include-titles
```

Or create a migration:

```python
def populate_title_author_keywords(apps, schema_editor):
    from books.utils.keywords import update_book_keywords
    BookMaster = apps.get_model('books', 'BookMaster')

    for bookmaster in BookMaster.objects.all():
        update_book_keywords(bookmaster)
```

### Keyword Weight Summary (Updated)

| Keyword Type | Weight | Rationale |
|-------------|--------|-----------|
| **Title** | 2.0 | Direct title match is most relevant |
| **Author** | 1.8 | Author search is common use case |
| Section | 1.5 | Broad categorization |
| Genre | 1.0 | Primary classification |
| Tag | 0.8 | Descriptive attributes |
| Entity | 0.6 | Specific names, may not be search terms |

### Files to Modify

1. **`books/choices.py`** - Add `TITLE` and `AUTHOR` to `KeywordType`
2. **`books/utils/keywords.py`** - Add extraction functions, update main function
3. **`books/signals/keywords.py`** - Add Book post_save signal handler
4. **`books/management/commands/populate_book_keywords.py`** - Update to include titles/authors

---

## Part 3: Entity Weight by Occurrence Frequency

### Problem

Currently all entities have the same weight (0.6), regardless of importance:
- Main protagonist appears in every chapter → weight 0.6
- Minor term mentioned once → weight 0.6

This makes search results less relevant since a book's main character has the same search weight as an obscure term.

### Current BookEntity Model

```python
class BookEntity(TimeStampModel):
    bookmaster = ForeignKey("BookMaster")
    entity_type = CharField(choices=EntityType.choices)  # character, place, term
    source_name = CharField(max_length=255)
    translations = JSONField()  # {"en": "...", "zh": "..."}
    first_chapter = ForeignKey("Chapter")  # Only tracks first appearance
```

**Missing**: No tracking of how often an entity appears across chapters.

### Solution

Add occurrence tracking to `BookEntity` and use it to calculate dynamic keyword weights.

### Step 1: Add occurrence fields to BookEntity (`books/models/context.py`)

```python
class BookEntity(TimeStampModel):
    bookmaster = models.ForeignKey("BookMaster", ...)
    entity_type = models.CharField(...)
    source_name = models.CharField(max_length=255)
    translations = models.JSONField(default=dict, blank=True)

    # REFACTORED: Renamed related_name from "entities" to "new_entities"
    first_chapter = models.ForeignKey(
        "Chapter",
        on_delete=models.CASCADE,
        related_name="new_entities",  # Was: "entities"
        help_text="Chapter where entity first appears"
    )

    # NEW: Occurrence tracking
    occurrence_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of chapters this entity appears in"
    )
    last_chapter = models.ForeignKey(
        "Chapter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="latest_entities",  # Simple and clear
        help_text="Most recent chapter where entity appears"
    )
```

### Chapter Entity Retrieval Patterns

After refactoring, here are the ways to retrieve entities from a Chapter:

| Method | Query | Description |
|--------|-------|-------------|
| **New entities** | `chapter.new_entities.all()` | Entities that first appeared in this chapter |
| **Latest entities** | `chapter.latest_entities.all()` | Entities whose most recent mention is in this chapter |
| **All entities** | Via ChapterContext | Entities mentioned in this chapter (from `context.key_terms`) |

```python
# Examples:

# 1. Get entities introduced in Chapter 1
chapter_1 = Chapter.objects.get(...)
new_in_ch1 = chapter_1.new_entities.all()

# 2. Get entities last seen in Chapter 50
chapter_50 = Chapter.objects.get(...)
last_seen_in_ch50 = chapter_50.latest_entities.all()

# 3. Get ALL entities mentioned in a specific chapter (via ChapterContext)
context = chapter.context  # OneToOne relation
all_entity_names = (
    context.key_terms.get('characters', []) +
    context.key_terms.get('places', []) +
    context.key_terms.get('terms', [])
)
# Then lookup BookEntity objects:
all_entities = BookEntity.objects.filter(
    bookmaster=chapter.book.bookmaster,
    source_name__in=all_entity_names
)
```

**Note**: To get all entities mentioned in a chapter (not just first/last), you must use ChapterContext.key_terms since BookEntity only tracks first and last appearance.

### Step 2: Update ChapterContext._create_book_entities()

```python
def _create_book_entities(self):
    """Create or update BookEntity records from stored key_terms"""
    entity_mappings = [
        (self.key_terms.get("characters", []), EntityType.CHARACTER),
        (self.key_terms.get("places", []), EntityType.PLACE),
        (self.key_terms.get("terms", []), EntityType.TERM),
    ]

    entities = []
    for entity_list, entity_type in entity_mappings:
        for name in entity_list:
            entity, created = BookEntity.objects.get_or_create(
                bookmaster=self.chapter.book.bookmaster,
                source_name=name,
                defaults={
                    "entity_type": entity_type,
                    "first_chapter": self.chapter,
                    "last_chapter": self.chapter,
                    "occurrence_count": 1,
                    "translations": {},
                },
            )

            # UPDATE: Increment count if entity already exists
            if not created:
                entity.occurrence_count = models.F('occurrence_count') + 1
                entity.last_chapter = self.chapter
                entity.save(update_fields=['occurrence_count', 'last_chapter'])
                entity.refresh_from_db()  # Refresh to get actual count

            entities.append(entity)

    return entities
```

### Step 3: Calculate dynamic entity weight (`books/utils/keywords.py`)

```python
def _calculate_entity_weight(entity, total_chapters: int) -> float:
    """
    Calculate entity keyword weight based on occurrence frequency.

    Weight formula:
    - Base weight: 0.4
    - Frequency bonus: up to 0.6 based on occurrence ratio

    Examples (for a 100-chapter book):
    - Entity in 1 chapter:   0.4 + (1/100 * 0.6)   = 0.406
    - Entity in 10 chapters: 0.4 + (10/100 * 0.6)  = 0.46
    - Entity in 50 chapters: 0.4 + (50/100 * 0.6)  = 0.7
    - Entity in 100 chapters: 0.4 + (100/100 * 0.6) = 1.0

    Additional modifiers:
    - Characters get +0.1 bonus (protagonists are common search terms)
    - Places get +0.05 bonus
    """
    BASE_WEIGHT = 0.4
    MAX_FREQUENCY_BONUS = 0.6

    # Calculate frequency ratio (capped at 1.0)
    if total_chapters > 0:
        frequency_ratio = min(entity.occurrence_count / total_chapters, 1.0)
    else:
        frequency_ratio = 0.0

    weight = BASE_WEIGHT + (frequency_ratio * MAX_FREQUENCY_BONUS)

    # Entity type bonus
    if entity.entity_type == EntityType.CHARACTER:
        weight += 0.1
    elif entity.entity_type == EntityType.PLACE:
        weight += 0.05

    return min(weight, 1.1)  # Cap at 1.1


def _extract_entity_keywords(bookmaster, seen_keywords: Set) -> List[BookKeyword]:
    """Extract keywords from entities with dynamic weights based on occurrence."""
    keywords = []

    # Get total chapter count for frequency calculation
    total_chapters = bookmaster.books.aggregate(
        total=models.Count('chapters')
    )['total'] or 1

    # Get original language code
    original_lang = bookmaster.original_language.code if bookmaster.original_language else 'zh'

    # Get all entities for this bookmaster
    entities = bookmaster.entities.all()

    for entity in entities:
        # Calculate dynamic weight based on occurrence
        weight = _calculate_entity_weight(entity, total_chapters)

        # Map EntityType to KeywordType
        keyword_type_map = {
            EntityType.CHARACTER: KeywordType.ENTITY_CHARACTER,
            EntityType.PLACE: KeywordType.ENTITY_PLACE,
            EntityType.TERM: KeywordType.ENTITY_TERM,
        }
        keyword_type = keyword_type_map.get(entity.entity_type, KeywordType.ENTITY_TERM)

        # Add primary entity name (source_name)
        _add_keyword(
            keywords, seen_keywords, bookmaster,
            entity.source_name, keyword_type, original_lang, weight
        )

        # Add translated entity names (same weight)
        if entity.translations:
            for lang_code, translated_name in entity.translations.items():
                if translated_name:
                    _add_keyword(
                        keywords, seen_keywords, bookmaster,
                        translated_name, keyword_type, lang_code, weight
                    )

    return keywords
```

### Step 4: Migration

```python
# Migration to add new fields
class Migration(migrations.Migration):
    dependencies = [
        ('books', 'previous_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookentity',
            name='occurrence_count',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='bookentity',
            name='last_chapter',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=models.SET_NULL,
                related_name='last_mentioned_entities',
                to='books.chapter',
            ),
        ),
    ]
```

### Step 5: Helper function to rebuild entity data (`books/utils/entities.py`)

When ChapterContext changes (re-analysis, manual edits, chapter deletion), we need to recalculate all entity data for the bookmaster:

```python
# books/utils/entities.py
from django.db import models, transaction
from books.models import BookEntity, ChapterContext, Chapter
from books.choices import EntityType


def rebuild_bookmaster_entities(bookmaster):
    """
    Rebuild all entity data for a bookmaster from ChapterContext records.

    This function:
    1. Scans all ChapterContext records for the bookmaster
    2. Collects entity occurrences with first/last chapter info
    3. Creates new entities, updates existing ones, removes orphaned ones

    Use cases:
    - ChapterContext re-analyzed (key_terms changed)
    - Chapter deleted
    - Manual entity cleanup
    - Data migration/repair

    Args:
        bookmaster: BookMaster instance to rebuild entities for

    Returns:
        dict: Summary of changes {created, updated, deleted}
    """
    # Get all chapters ordered by chapter_number
    chapters = Chapter.objects.filter(
        book__bookmaster=bookmaster
    ).select_related(
        'chaptermaster'
    ).order_by('chaptermaster__chapter_number')

    # Build entity occurrence map from ChapterContext
    # Structure: {source_name: {type, first_chapter, last_chapter, count}}
    entity_map = {}

    for chapter in chapters:
        try:
            context = chapter.context
        except ChapterContext.DoesNotExist:
            continue

        entity_mappings = [
            (context.key_terms.get("characters", []), EntityType.CHARACTER),
            (context.key_terms.get("places", []), EntityType.PLACE),
            (context.key_terms.get("terms", []), EntityType.TERM),
        ]

        for entity_list, entity_type in entity_mappings:
            for name in entity_list:
                if name not in entity_map:
                    # First occurrence
                    entity_map[name] = {
                        'entity_type': entity_type,
                        'first_chapter': chapter,
                        'last_chapter': chapter,
                        'occurrence_count': 1,
                    }
                else:
                    # Subsequent occurrence
                    entity_map[name]['last_chapter'] = chapter
                    entity_map[name]['occurrence_count'] += 1

    # Apply changes in a transaction
    stats = {'created': 0, 'updated': 0, 'deleted': 0}

    with transaction.atomic():
        # Get existing entities
        existing_entities = {
            e.source_name: e
            for e in BookEntity.objects.filter(bookmaster=bookmaster)
        }

        # Process entity map
        for source_name, data in entity_map.items():
            if source_name in existing_entities:
                # Update existing entity
                entity = existing_entities[source_name]
                entity.entity_type = data['entity_type']
                entity.first_chapter = data['first_chapter']
                entity.last_chapter = data['last_chapter']
                entity.occurrence_count = data['occurrence_count']
                entity.save(update_fields=[
                    'entity_type', 'first_chapter', 'last_chapter', 'occurrence_count'
                ])
                stats['updated'] += 1
                del existing_entities[source_name]  # Mark as processed
            else:
                # Create new entity
                BookEntity.objects.create(
                    bookmaster=bookmaster,
                    source_name=source_name,
                    entity_type=data['entity_type'],
                    first_chapter=data['first_chapter'],
                    last_chapter=data['last_chapter'],
                    occurrence_count=data['occurrence_count'],
                    translations={},
                )
                stats['created'] += 1

        # Delete orphaned entities (no longer in any ChapterContext)
        orphaned_names = list(existing_entities.keys())
        if orphaned_names:
            deleted_count, _ = BookEntity.objects.filter(
                bookmaster=bookmaster,
                source_name__in=orphaned_names
            ).delete()
            stats['deleted'] = deleted_count

    return stats


def rebuild_single_chapter_entities(chapter):
    """
    Convenience function to rebuild entities after a single chapter's context changes.

    This triggers a full bookmaster rebuild since entity first/last chapters
    may shift when any chapter's context changes.
    """
    if chapter.book and chapter.book.bookmaster:
        return rebuild_bookmaster_entities(chapter.book.bookmaster)
    return {'created': 0, 'updated': 0, 'deleted': 0}
```

### Step 6: Signal to trigger rebuild on ChapterContext change

```python
# books/signals/entities.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from books.models import ChapterContext
from books.utils.entities import rebuild_single_chapter_entities


@receiver(post_save, sender=ChapterContext)
def rebuild_entities_on_context_save(sender, instance, **kwargs):
    """Rebuild entity data when ChapterContext is saved (created or updated)."""
    rebuild_single_chapter_entities(instance.chapter)


@receiver(post_delete, sender=ChapterContext)
def rebuild_entities_on_context_delete(sender, instance, **kwargs):
    """Rebuild entity data when ChapterContext is deleted."""
    rebuild_single_chapter_entities(instance.chapter)
```

### Step 7: Management command for bulk operations

```python
# books/management/commands/rebuild_entities.py
from django.core.management.base import BaseCommand
from books.models import BookMaster
from books.utils.entities import rebuild_bookmaster_entities


class Command(BaseCommand):
    help = 'Rebuild entity data from ChapterContext for all or specific bookmasters'

    def add_arguments(self, parser):
        parser.add_argument(
            '--bookmaster-id',
            type=int,
            help='Rebuild entities for a specific bookmaster ID'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Rebuild entities for all bookmasters'
        )

    def handle(self, *args, **options):
        if options['bookmaster_id']:
            bookmasters = BookMaster.objects.filter(id=options['bookmaster_id'])
        elif options['all']:
            bookmasters = BookMaster.objects.all()
        else:
            self.stderr.write('Please specify --bookmaster-id or --all')
            return

        total_stats = {'created': 0, 'updated': 0, 'deleted': 0}

        for bookmaster in bookmasters:
            self.stdout.write(f'Processing: {bookmaster.canonical_title}')
            stats = rebuild_bookmaster_entities(bookmaster)
            self.stdout.write(
                f'  Created: {stats["created"]}, '
                f'Updated: {stats["updated"]}, '
                f'Deleted: {stats["deleted"]}'
            )
            for key in total_stats:
                total_stats[key] += stats[key]

        self.stdout.write(self.style.SUCCESS(
            f'\nTotal - Created: {total_stats["created"]}, '
            f'Updated: {total_stats["updated"]}, '
            f'Deleted: {total_stats["deleted"]}'
        ))
```

### Entity Rebuild Use Cases

| Trigger | Action | Function |
|---------|--------|----------|
| ChapterContext saved | Auto-rebuild bookmaster entities | Signal → `rebuild_single_chapter_entities()` |
| ChapterContext deleted | Auto-rebuild bookmaster entities | Signal → `rebuild_single_chapter_entities()` |
| Chapter deleted | Cascade deletes context, triggers rebuild | Signal chain |
| Manual repair | Run management command | `python manage.py rebuild_entities --all` |
| Data migration | Run management command | `python manage.py rebuild_entities --all` |

### Entity Weight Summary (Dynamic)

| Entity Type | Base Weight | Frequency Bonus | Type Bonus | Max Weight |
|-------------|-------------|-----------------|------------|------------|
| Character | 0.4 | 0.0 - 0.6 | +0.1 | 1.1 |
| Place | 0.4 | 0.0 - 0.6 | +0.05 | 1.05 |
| Term | 0.4 | 0.0 - 0.6 | 0 | 1.0 |

**Examples** (100-chapter book):
| Entity | Occurrences | Calculated Weight |
|--------|-------------|-------------------|
| Main protagonist (character) | 100 | 0.4 + 0.6 + 0.1 = **1.1** |
| Major location (place) | 50 | 0.4 + 0.3 + 0.05 = **0.75** |
| Minor term | 2 | 0.4 + 0.012 = **0.41** |

### Files to Modify

1. **`books/models/context.py`** - Add `occurrence_count`, `last_chapter` fields; rename `first_chapter.related_name`
2. **`books/utils/keywords.py`** - Add `_calculate_entity_weight()`, update `_extract_entity_keywords()`
3. **`books/utils/entities.py`** - NEW: Add `rebuild_bookmaster_entities()`, `rebuild_single_chapter_entities()`
4. **`books/signals/entities.py`** - NEW: Add signals for ChapterContext save/delete
5. **`books/migrations/`** - New migration for BookEntity fields + related_name change
6. **`books/management/commands/rebuild_entities.py`** - NEW: Management command for bulk rebuild

---

## Testing Checklist

### Part 1: View Refactoring
- [ ] Global search works: `/<lang>/search/?q=fantasy`
- [ ] Global search with section filter: `/<lang>/search/?q=fantasy&section=fiction`
- [ ] Section search works: `/<lang>/fiction/search/?q=cultivation`
- [ ] Section search with genre filter: `/<lang>/fiction/search/?q=cultivation&genre=wuxia`
- [ ] Pagination works on both views
- [ ] Search order (relevance ranking) preserved
- [ ] Genre hierarchy displays correctly in section search
- [ ] Empty query returns empty results gracefully

### Part 2: Title/Author Keywords
- [ ] Search by book title returns correct results
- [ ] Search by author name returns correct results
- [ ] Title matches rank higher than genre/tag matches
- [ ] Multi-language title search works (e.g., Chinese title finds book)
- [ ] Keywords rebuild when Book.title changes
- [ ] Keywords rebuild when Book.author changes
- [ ] Migration successfully populates keywords for existing books

### Part 3: Entity Occurrence Weights
- [ ] BookEntity.occurrence_count increments on each chapter analysis
- [ ] BookEntity.last_chapter updates correctly
- [ ] Main protagonist (high occurrence) has higher weight than minor term
- [ ] Character entities have +0.1 type bonus
- [ ] Place entities have +0.05 type bonus
- [ ] Search for main character ranks book higher than search for minor term
- [ ] `chapter.new_entities` returns entities first introduced in chapter
- [ ] `chapter.latest_entities` returns entities last seen in chapter

### Part 3b: Entity Rebuild Function
- [ ] `rebuild_bookmaster_entities()` creates new entities from ChapterContext
- [ ] `rebuild_bookmaster_entities()` updates existing entities (first/last chapter, count)
- [ ] `rebuild_bookmaster_entities()` deletes orphaned entities not in any ChapterContext
- [ ] Signal triggers rebuild on ChapterContext save
- [ ] Signal triggers rebuild on ChapterContext delete
- [ ] Management command `rebuild_entities --all` works
- [ ] Management command `rebuild_entities --bookmaster-id=X` works
- [ ] Translations preserved when entity is updated (not overwritten)
