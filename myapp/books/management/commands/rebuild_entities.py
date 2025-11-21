"""
Management command to rebuild entity data from ChapterContext records.

Usage:
    # Rebuild entities for all bookmasters
    python manage.py rebuild_entities --all

    # Rebuild entities for a specific bookmaster
    python manage.py rebuild_entities --bookmaster-id=1

    # Also rebuild keywords after entity rebuild
    python manage.py rebuild_entities --all --rebuild-keywords
"""

from django.core.management.base import BaseCommand

from books.models import BookMaster
from books.utils.entities import rebuild_bookmaster_entities
from books.utils.keywords import update_book_keywords


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
        parser.add_argument(
            '--rebuild-keywords',
            action='store_true',
            help='Also rebuild keywords after entity rebuild (to update entity weights)'
        )

    def handle(self, *args, **options):
        if options['bookmaster_id']:
            bookmasters = BookMaster.objects.filter(id=options['bookmaster_id'])
            if not bookmasters.exists():
                self.stderr.write(
                    self.style.ERROR(f"BookMaster with ID {options['bookmaster_id']} not found")
                )
                return
        elif options['all']:
            bookmasters = BookMaster.objects.all()
        else:
            self.stderr.write(
                self.style.ERROR('Please specify --bookmaster-id or --all')
            )
            return

        total_stats = {'created': 0, 'updated': 0, 'deleted': 0}
        keyword_count = 0

        for bookmaster in bookmasters:
            self.stdout.write(f'Processing: {bookmaster.canonical_title}')

            # Rebuild entities
            stats = rebuild_bookmaster_entities(bookmaster)
            self.stdout.write(
                f'  Entities - Created: {stats["created"]}, '
                f'Updated: {stats["updated"]}, '
                f'Deleted: {stats["deleted"]}'
            )

            for key in total_stats:
                total_stats[key] += stats[key]

            # Optionally rebuild keywords
            if options['rebuild_keywords']:
                kw_count = update_book_keywords(bookmaster)
                self.stdout.write(f'  Keywords rebuilt: {kw_count}')
                keyword_count += kw_count

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Total Entities - Created: {total_stats["created"]}, '
            f'Updated: {total_stats["updated"]}, '
            f'Deleted: {total_stats["deleted"]}'
        ))

        if options['rebuild_keywords']:
            self.stdout.write(self.style.SUCCESS(
                f'Total Keywords rebuilt: {keyword_count}'
            ))
