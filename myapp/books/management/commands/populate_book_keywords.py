"""
Management command to populate BookKeyword records for all BookMaster instances.

This command extracts keywords from existing taxonomy (sections, genres, tags)
and entities (characters, places, terms) to populate the BookKeyword table.

Usage:
    python manage.py populate_book_keywords
    python manage.py populate_book_keywords --force  # Re-populate even if keywords exist
"""

from django.core.management.base import BaseCommand
from books.models import BookMaster
from books.utils import update_book_keywords


class Command(BaseCommand):
    help = "Populate BookKeyword records for all BookMaster instances"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-population even if keywords already exist',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)

        # Get all bookmasters
        bookmasters = BookMaster.objects.all()
        total_count = bookmasters.count()

        if total_count == 0:
            self.stdout.write(self.style.WARNING("No bookmasters found."))
            return

        self.stdout.write(f"Found {total_count} bookmasters.")

        if force:
            self.stdout.write(self.style.WARNING("Force mode: Re-populating all keywords"))

        # Process each bookmaster
        processed = 0
        total_keywords = 0
        errors = 0

        for bookmaster in bookmasters.iterator():
            try:
                # Check if keywords already exist
                if not force and bookmaster.keywords.exists():
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Skipping '{bookmaster.canonical_title}' (keywords already exist, use --force to re-populate)"
                        )
                    )
                    processed += 1
                    continue

                # Populate keywords
                keyword_count = update_book_keywords(bookmaster)
                total_keywords += keyword_count
                processed += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ '{bookmaster.canonical_title}': {keyword_count} keywords"
                    )
                )

                # Print progress every 10 books
                if processed % 10 == 0:
                    self.stdout.write(f"  Progress: {processed}/{total_count} bookmasters...")

            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  ✗ Failed for '{bookmaster.canonical_title}': {e}"
                    )
                )
                # Continue with next bookmaster
                continue

        # Final summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"✓ Successfully processed {processed}/{total_count} bookmasters"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"✓ Created {total_keywords} keyword records"
        ))

        if errors > 0:
            self.stdout.write(self.style.WARNING(
                f"⚠ {errors} bookmasters had errors"
            ))
