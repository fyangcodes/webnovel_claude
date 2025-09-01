from django.db import models


class Role(models.TextChoices):
    READER = "reader", "Reader"
    TRANSLATOR = "translator", "Translator"
    ADMIN = "admin", "Admin"
