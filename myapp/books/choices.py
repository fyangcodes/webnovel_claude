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


class CountUnits(models.TextChoices):
    WORDS = "words", "Words"
    CHARS = "chars", "Characters"


class Rating(models.TextChoices):
    EVERYONE = "everyone", "Everyone"
    TEEN = "teen", "Teen (13+)"
    MATURE = "mature", "Mature (16+)"
    ADULT = "adult", "Adult (18+)"
