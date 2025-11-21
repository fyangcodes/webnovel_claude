from django.db import models


class BookProgress(models.TextChoices):
    DRAFT = "draft", "Draft"
    ONGOING = "ongoing", "Ongoing"
    COMPLETED = "completed", "Completed"


class ChapterProgress(models.TextChoices):
    DRAFT = "draft", "Draft"
    TRANSLATING = "translating", "Translating"
    COMPLETED = "completed", "Completed"


class ProcessingStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class CountUnit(models.TextChoices):
    WORDS = "words", "Words"
    CHARS = "chars", "Characters"


class Rating(models.TextChoices):
    EVERYONE = "everyone", "Everyone"
    TEEN = "teen", "Teen (13+)"
    MATURE = "mature", "Mature (16+)"
    ADULT = "adult", "Adult (18+)"


class EntityType(models.TextChoices):
    CHARACTER = "character", "Character"
    PLACE = "place", "Place"
    TERM = "term", "Term"


class TagCategory(models.TextChoices):
    """Categories for organizing tags"""
    PROTAGONIST = "protagonist", "Protagonist Type"
    NARRATIVE = "narrative", "Narrative Style"
    THEME = "theme", "Theme"
    TROPE = "trope", "Trope"
    CONTENT_WARNING = "content_warning", "Content Warning"
    AUDIENCE = "audience", "Target Audience"
    SETTING = "setting", "Setting"


class TagSource(models.TextChoices):
    """Source of tag assignment"""
    MANUAL = "manual", "Manual"
    AI_SUGGESTED = "ai_suggested", "AI Suggested"
    AI_AUTO = "ai_auto", "AI Automatic"
    COMMUNITY = "community", "Community"


class KeywordType(models.TextChoices):
    """Types of keywords for search indexing"""
    SECTION = "section", "Section"
    GENRE = "genre", "Genre"
    TAG = "tag", "Tag"
    ENTITY_CHARACTER = "entity_character", "Character"
    ENTITY_PLACE = "entity_place", "Place"
    ENTITY_TERM = "entity_term", "Term"
    TITLE = "title", "Title"
    AUTHOR = "author", "Author"
