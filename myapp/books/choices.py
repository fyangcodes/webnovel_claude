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


class MediaType(models.TextChoices):
    IMAGE = "image", "Image"
    AUDIO = "audio", "Audio"
    VIDEO = "video", "Video"
    DOCUMENT = "document", "Document"
    OTHER = "other", "Other"


class ParagraphStyle(models.TextChoices):
    SINGLE_NEWLINE = "single_newline", "Single Newline"
    DOUBLE_NEWLINE = "double_newline", "Double Newline"
    AUTO_DETECT = "auto_detect", "Auto Detect"


class ChangeType(models.TextChoices):
    TRANSLATION = "translation", "Translation"
    EDIT = "edit", "Edit/Correction"
    OTHER = "other", "Other"


class Rating(models.TextChoices):
    EVERYONE = "everyone", "Everyone"
    TEEN = "teen", "Teen (13+)"
    MATURE = "mature", "Mature (16+)"
    ADULT = "adult", "Adult (18+)"
