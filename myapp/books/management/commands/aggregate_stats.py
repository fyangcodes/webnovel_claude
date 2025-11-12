"""
Management command to manually aggregate stats from Redis to PostgreSQL.
Usage: python manage.py aggregate_stats
"""

from django.core.management.base import BaseCommand
from books.tasks import aggregate_stats_hourly


class Command(BaseCommand):
    help = 'Manually aggregate stats from Redis to PostgreSQL'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Aggregating stats from Redis to PostgreSQL...'))

        result = aggregate_stats_hourly()

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Stats aggregation complete!\n"
                f"  - Chapters updated: {result['chapters']}\n"
                f"  - Books updated: {result['books']}"
            )
        )
