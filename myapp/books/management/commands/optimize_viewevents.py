"""
Optimize ViewEvent storage to reduce database size.

Usage:
    python manage.py optimize_viewevents --analyze   # Check current usage
    python manage.py optimize_viewevents --truncate  # Delete old events (WARNING!)
    python manage.py optimize_viewevents --clean-ua  # Remove user agent data
"""

import logging
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Optimize ViewEvent storage to reduce database bloat"

    def add_arguments(self, parser):
        parser.add_argument(
            "--analyze",
            action="store_true",
            help="Analyze ViewEvent storage usage",
        )
        parser.add_argument(
            "--truncate",
            action="store_true",
            help="Delete ViewEvents older than specified days (WARNING: Data loss!)",
        )
        parser.add_argument(
            "--clean-ua",
            action="store_true",
            help="Remove user_agent data to save space (keeps session_key for analytics)",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Days to keep for --truncate (default: 30)",
        )

    def handle(self, *args, **options):
        """Execute optimization operations."""
        if options["analyze"]:
            self.analyze_viewevents()

        if options["clean_ua"]:
            self.clean_user_agents()

        if options["truncate"]:
            self.truncate_old_events(days=options["days"])

        if not any([options["analyze"], options["truncate"], options["clean_ua"]]):
            self.stdout.write(
                self.style.WARNING("No action specified.")
            )
            self.stdout.write("\nUsage:")
            self.stdout.write("  python manage.py optimize_viewevents --analyze")
            self.stdout.write("  python manage.py optimize_viewevents --clean-ua")
            self.stdout.write("  python manage.py optimize_viewevents --truncate --days=30")

    def analyze_viewevents(self):
        """Analyze ViewEvent table and estimate savings."""
        self.stdout.write(self.style.SUCCESS("\n=== ViewEvent Storage Analysis ===\n"))

        from books.models import ViewEvent

        total_count = ViewEvent.objects.count()
        self.stdout.write(f"Total ViewEvents: {total_count:,}")

        if total_count == 0:
            self.stdout.write("No ViewEvents found.")
            return

        with connection.cursor() as cursor:
            if connection.vendor == "postgresql":
                # Table size
                cursor.execute("""
                    SELECT
                        pg_size_pretty(pg_total_relation_size('books_viewevent')) AS total_size,
                        pg_size_pretty(pg_relation_size('books_viewevent')) AS table_size,
                        pg_size_pretty(pg_total_relation_size('books_viewevent') - pg_relation_size('books_viewevent')) AS indexes_size
                """)
                total_size, table_size, indexes_size = cursor.fetchone()

                self.stdout.write(f"\nStorage Usage:")
                self.stdout.write(f"  Total (table + indexes): {total_size}")
                self.stdout.write(f"  Table data: {table_size}")
                self.stdout.write(f"  Indexes: {indexes_size}")

                # User agent field analysis
                cursor.execute("""
                    SELECT
                        COUNT(*) as records_with_ua,
                        AVG(LENGTH(user_agent))::int as avg_ua_length,
                        MAX(LENGTH(user_agent)) as max_ua_length,
                        pg_size_pretty(SUM(LENGTH(user_agent))::bigint) as total_ua_size
                    FROM books_viewevent
                    WHERE user_agent IS NOT NULL AND user_agent != ''
                """)
                result = cursor.fetchone()
                if result and result[0] > 0:
                    records, avg_len, max_len, total_size_ua = result
                    self.stdout.write(f"\nUser-Agent Field:")
                    self.stdout.write(f"  Records with user_agent: {records:,}")
                    self.stdout.write(f"  Average length: {avg_len:,} bytes")
                    self.stdout.write(f"  Max length: {max_len:,} bytes")
                    self.stdout.write(f"  Total size: {total_size_ua}")
                    self.stdout.write(
                        self.style.WARNING(f"\n  💡 Potential savings: ~{total_size_ua} by removing user_agent")
                    )

                # Referrer field analysis
                cursor.execute("""
                    SELECT
                        COUNT(*) as records_with_ref,
                        AVG(LENGTH(referrer))::int as avg_ref_length,
                        pg_size_pretty(SUM(LENGTH(referrer))::bigint) as total_ref_size
                    FROM books_viewevent
                    WHERE referrer IS NOT NULL AND referrer != ''
                """)
                result = cursor.fetchone()
                if result and result[0] > 0:
                    records, avg_len, total_size_ref = result
                    self.stdout.write(f"\nReferrer Field:")
                    self.stdout.write(f"  Records with referrer: {records:,}")
                    self.stdout.write(f"  Average length: {avg_len:,} bytes")
                    self.stdout.write(f"  Total size: {total_size_ref}")

                # Age distribution
                cursor.execute("""
                    SELECT
                        CASE
                            WHEN viewed_at > NOW() - INTERVAL '7 days' THEN '< 7 days'
                            WHEN viewed_at > NOW() - INTERVAL '30 days' THEN '7-30 days'
                            WHEN viewed_at > NOW() - INTERVAL '90 days' THEN '30-90 days'
                            ELSE '> 90 days'
                        END as age_range,
                        COUNT(*) as count,
                        pg_size_pretty(SUM(LENGTH(COALESCE(user_agent, '')) + LENGTH(COALESCE(referrer, '')))::bigint) as text_size
                    FROM books_viewevent
                    GROUP BY age_range
                    ORDER BY
                        CASE age_range
                            WHEN '< 7 days' THEN 1
                            WHEN '7-30 days' THEN 2
                            WHEN '30-90 days' THEN 3
                            ELSE 4
                        END
                """)

                self.stdout.write(f"\nAge Distribution:")
                self.stdout.write(f"{'Age Range':<15} {'Count':>10} {'Text Data Size':>15}")
                self.stdout.write("-" * 45)
                for age_range, count, size in cursor.fetchall():
                    self.stdout.write(f"{age_range:<15} {count:>10,} {size:>15}")

        # Recommendations
        self.stdout.write(self.style.SUCCESS("\n=== Recommendations ===\n"))

        old_count = ViewEvent.objects.filter(
            viewed_at__lt=timezone.now() - timedelta(days=30)
        ).count()

        if old_count > 1000:
            self.stdout.write(
                f"📅 Delete events older than 30 days: {old_count:,} records"
            )
            self.stdout.write("   Command: python manage.py optimize_viewevents --truncate --days=30")

        if total_count > 1000:
            self.stdout.write(
                "🗑️  Remove user_agent data to save ~50% space"
            )
            self.stdout.write("   Command: python manage.py optimize_viewevents --clean-ua")

        self.stdout.write(
            "\n🔧 After cleanup, run VACUUM:"
        )
        self.stdout.write("   Command: python manage.py db_cleanup --vacuum")

    def clean_user_agents(self):
        """Remove user_agent and referrer data to save space."""
        from books.models import ViewEvent

        self.stdout.write(self.style.WARNING("\n=== Cleaning User-Agent Data ===\n"))

        count = ViewEvent.objects.filter(
            user_agent__isnull=False
        ).count()

        self.stdout.write(f"Found {count:,} ViewEvents with user_agent data")

        if count == 0:
            self.stdout.write("Nothing to clean.")
            return

        confirm = input(f"\nThis will set user_agent and referrer to NULL for {count:,} records.\nContinue? (yes/no): ")

        if confirm.lower() != "yes":
            self.stdout.write("Cancelled.")
            return

        # Update in batches to avoid timeout
        batch_size = 1000
        updated = 0

        self.stdout.write("Cleaning in batches...")

        while True:
            batch_updated = ViewEvent.objects.filter(
                user_agent__isnull=False
            )[:batch_size].update(
                user_agent=None,
                referrer=None
            )

            if batch_updated == 0:
                break

            updated += batch_updated
            self.stdout.write(f"  Cleaned {updated:,} / {count:,} records...", ending='\r')

        self.stdout.write(f"\n✅ Cleaned {updated:,} records")
        self.stdout.write("\nRun VACUUM to reclaim disk space:")
        self.stdout.write("  python manage.py db_cleanup --vacuum")

    def truncate_old_events(self, days=30):
        """Delete ViewEvents older than specified days."""
        from books.models import ViewEvent

        self.stdout.write(
            self.style.WARNING(f"\n=== Deleting ViewEvents Older Than {days} Days ===\n")
        )

        cutoff_date = timezone.now() - timedelta(days=days)
        old_events = ViewEvent.objects.filter(viewed_at__lt=cutoff_date)
        count = old_events.count()

        if count == 0:
            self.stdout.write(f"No ViewEvents older than {days} days found.")
            return

        self.stdout.write(f"Found {count:,} ViewEvents older than {cutoff_date.date()}")

        confirm = input(f"\n⚠️  This will DELETE {count:,} records permanently!\nContinue? (yes/no): ")

        if confirm.lower() != "yes":
            self.stdout.write("Cancelled.")
            return

        self.stdout.write("Deleting...")
        deleted_count, _ = old_events.delete()

        self.stdout.write(self.style.SUCCESS(f"\n✅ Deleted {deleted_count:,} old ViewEvents"))
        self.stdout.write("\nRun VACUUM to reclaim disk space:")
        self.stdout.write("  python manage.py db_cleanup --vacuum")
