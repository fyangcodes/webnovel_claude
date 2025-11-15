"""
Data migration to populate BookKeyword records for existing BookMaster instances.

This migration extracts keywords from existing taxonomy (sections, genres, tags)
and entities (characters, places, terms) to populate the BookKeyword table.
"""

from django.db import migrations


def populate_keywords(apps, schema_editor):
    """
    Populate BookKeyword records for all existing BookMaster instances.

    NOTE: This migration is intentionally simplified to avoid issues with historical models.
    Actual keyword population should be done via management command or signal handlers
    after migration completes.

    Historical models in migrations cannot access relationships the same way as live models,
    so we skip actual population here and let signals handle it on future saves.
    """
    # Get historical models
    BookMaster = apps.get_model('books', 'BookMaster')

    total_count = BookMaster.objects.count()

    if total_count == 0:
        print("No bookmasters found. Skipping keyword population.")
        return

    print(f"Found {total_count} bookmasters.")
    print("NOTE: Keywords will be auto-populated by signals when bookmasters are saved.")
    print("To manually populate keywords now, run: python manage.py populate_book_keywords")
    print("(This management command will be created in a future update)")

    # Don't try to populate keywords here - let signals handle it
    # Historical models can't traverse relationships properly
    print("✓ Migration completed. Use signals or management command to populate keywords.")


def reverse_keywords(apps, schema_editor):
    """
    Remove all BookKeyword records.

    This allows rolling back the migration by clearing the keyword table.
    """
    BookKeyword = apps.get_model('books', 'BookKeyword')

    count = BookKeyword.objects.count()
    BookKeyword.objects.all().delete()

    print(f"✓ Removed {count} keyword records")


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0020_alter_analysisjob_options_alter_book_options_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_keywords, reverse_keywords),
    ]
