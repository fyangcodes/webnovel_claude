"""
Management command to initialize stats models for existing chapters and books.
"""

from django.core.management.base import BaseCommand
from books.models import Chapter, Book, ChapterStats, BookStats


class Command(BaseCommand):
    help = "Initialize stats models for existing chapters and books"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating it",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))

        # Create ChapterStats for chapters without stats
        chapters_without_stats = Chapter.objects.filter(stats__isnull=True)
        chapter_count = chapters_without_stats.count()

        if dry_run:
            self.stdout.write(f"Would create stats for {chapter_count} chapters")
        else:
            for chapter in chapters_without_stats:
                ChapterStats.objects.create(chapter=chapter)
            self.stdout.write(
                self.style.SUCCESS(f"✓ Created stats for {chapter_count} chapters")
            )

        # Create BookStats for books without stats
        books_without_stats = Book.objects.filter(stats__isnull=True)
        book_count = books_without_stats.count()

        if dry_run:
            self.stdout.write(f"Would create stats for {book_count} books")
        else:
            for book in books_without_stats:
                BookStats.objects.create(book=book)
            self.stdout.write(
                self.style.SUCCESS(f"✓ Created stats for {book_count} books")
            )

        # Summary
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDRY RUN: Would create {chapter_count} chapter stats "
                    f"and {book_count} book stats"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Successfully initialized stats for {chapter_count} chapters "
                    f"and {book_count} books"
                )
            )
