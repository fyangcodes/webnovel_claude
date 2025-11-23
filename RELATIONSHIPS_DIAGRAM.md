# Model Relationships Diagram

## Data Model Hierarchy

```
Book (Language-Specific)
  ├── BookMaster (Language-Independent)
  │   ├── Section (ONE-to-MANY from Section's perspective)
  │   │   ├── name: "Fiction", "BL", "GL"
  │   │   ├── translations: {language_code: {name, description}}
  │   │   └── genres: All genres in this section
  │   │
  │   ├── Author (ONE-to-MANY from Author's perspective)
  │   │   ├── name: Author's name
  │   │   ├── avatar: Profile image
  │   │   └── translations: {language_code: {name, description}}
  │   │
  │   ├── Genres (MANY-to-MANY through BookGenre)
  │   │   └── BookGenre (order, display position)
  │   │       └── Genre
  │   │           ├── name, slug
  │   │           ├── is_primary: True (main) or False (sub)
  │   │           ├── parent: Reference to primary genre (for sub-genres)
  │   │           ├── section: FK to Section
  │   │           └── translations: {language_code: {name, description}}
  │   │
  │   ├── Tags (MANY-to-MANY through BookTag)
  │   │   └── BookTag (confidence, source)
  │   │       └── Tag
  │   │           ├── name, slug
  │   │           ├── category: protagonist, narrative, theme, trope, etc.
  │   │           └── translations: {language_code: {name, description}}
  │   │
  │   └── Entities (ONE-to-MANY)
  │       └── BookEntity
  │           ├── entity_type: character, place, term
  │           ├── source_name: Original name
  │           ├── translations: {language_code: translated_name}
  │           ├── first_chapter: FK to Chapter
  │           ├── last_chapter: FK to Chapter
  │           └── occurrence_count: Chapters entity appears in
  │
  ├── Language
  │   ├── code: "en", "zh", "de", etc.
  │   ├── name, local_name
  │   ├── count_units: words or chars
  │   ├── wpm: reading speed
  │   └── is_public: visibility flag
  │
  └── Chapters (MANY)
      └── Chapter
          ├── title, content, slug
          ├── ChapterMaster (for translation synchronization)
          ├── word_count, character_count
          └── context: ChapterContext (AI analysis)
```

## Template Display Flow

### Book Card Partial
```
book_card.html
├── Section Badge (1)
│   └── bg-primary-custom (orange)
├── Genres (up to 2)
│   └── bg-secondary (gray) - sliced from book.bookmaster.genres
└── Modal on Info Button Click
    ├── Section Badge
    ├── All Genres with hierarchy
    ├── Stats (chapters, status, views)
    └── Read Now Link
```

### Book Detail Page
```
book_detail.html
├── Section Link
│   └── bg-primary-custom with icon
├── All Genres
│   └── bg-secondary with parent hierarchy
├── Tags by Category
│   ├── Category Name Header
│   └── Each Tag: bg-light text-dark border
└── Chapters List (paginated, 20 per page)
```

## View Context Flow

```
Request → View (detail_views.py)
  ↓
BaseReaderView.get_context_data()
  ├── current_language: Language object
  ├── languages: [Language] (cached)
  ├── sections: [Section] with localized_name (cached)
  ├── genres_hierarchical: {section_id: {primary: [...], sub: {...}}} (cached)
  ├── tags_by_category: {category: [Tag]} (cached)
  └── Localize all names based on language_code
  ↓
BaseBookDetailView.get_context_data()
  ├── genres: [Genre] with localized_name + parent_localized_name
  ├── tags_by_category: {category: [Tag]} with localized_name
  └── section_localized_name
  ↓
BookDetailView.get_context_data()
  ├── author, author_localized_name
  ├── chapters: Paginated QuerySet
  ├── total_chapters, total_words
  ├── total_chapter_views: Cached value
  └── last_update: DateTime
  ↓
Template Renders with All Context
```

## Localization Pattern

```
Model Instance (e.g., Genre)
  ├── name: "Fantasy" (default)
  ├── translations: {
  │     "en": {"name": "Fantasy"},
  │     "zh": {"name": "奇幻"},
  │     "ja": {"name": "ファンタジー"}
  │   }
  │
  └── Method: get_localized_name(language_code)
      └── Returns translated name or falls back to default
```

Used in templates as: `{{ genre.localized_name }}`

## Badge Styling Map

```
Component          Class                  Color        Usage
─────────────────────────────────────────────────────────────
Section            bg-primary-custom      Orange       On cards & detail
Primary Genre      bg-secondary           Gray         On cards & detail
Sub-Genre          bg-secondary           Gray         Detail only
Tag                bg-light text-dark     Light gray   Detail only
                   border

Progress Badge     bg-primary              (Bootstrap)  Status
                   bg-success              (Bootstrap)  Completed
                   bg-danger               (Bootstrap)  Draft
```

## Caching Strategy

```
Per-Book (dynamic):
  ├── published_chapters_count: cache.get_cached_chapter_count(book_id)
  └── total_chapter_views: cache.get_cached_total_chapter_views(book_id)

Global (static):
  ├── languages: cache.get_cached_languages(user)
  ├── sections: cache.get_cached_sections(user)
  ├── genres_hierarchical: cache.get_cached_genres()
  ├── genres_flat: cache.get_cached_genres_flat()
  └── tags_by_category: cache.get_cached_tags()
```

## Relationships Summary Table

| Source         | Target          | Type | Through Model | Cardinality | Notes |
|----------------|-----------------|------|---------------|-------------|-------|
| BookMaster     | Section         | FK   | -             | Many-to-One | Nullable |
| BookMaster     | Author          | FK   | -             | Many-to-One | Nullable |
| BookMaster     | Genre           | M2M  | BookGenre     | Many-to-Many | Ordered, validates section match |
| BookMaster     | Tag             | M2M  | BookTag       | Many-to-Many | Has confidence & source |
| BookMaster     | BookEntity      | 1-M  | -             | One-to-Many | Characters, places, terms |
| Genre          | Section         | FK   | -             | Many-to-One | For section-level uniqueness |
| Genre          | Genre (parent)  | FK   | -             | Many-to-One | Self-reference for hierarchy |
| Book           | BookMaster      | FK   | -             | Many-to-One | Language-specific version |
| Book           | Language        | FK   | -             | Many-to-One | Which language this book is in |
| Chapter        | Book            | FK   | -             | Many-to-One | Chapters belong to specific language version |
| Chapter        | ChapterMaster   | FK   | -             | Many-to-One | Links to master chapter |

