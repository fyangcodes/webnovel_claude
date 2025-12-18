"""
Database cleanup and disk space management command.

Usage:
    python manage.py db_cleanup --check      # Check disk usage
    python manage.py db_cleanup --vacuum     # Run VACUUM to reclaim space
    python manage.py db_cleanup --clean-old  # Delete old data (use with caution!)
"""

import logging
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Database cleanup and disk space management"

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Check database size and table sizes",
        )
        parser.add_argument(
            "--vacuum",
            action="store_true",
            help="Run VACUUM to reclaim disk space (PostgreSQL only)",
        )
        parser.add_argument(
            "--clean-old",
            action="store_true",
            help="Clean old/expired data (WARNING: Deletes data!)",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Days to keep for --clean-old (default: 90)",
        )

    def handle(self, *args, **options):
        """Execute database cleanup operations."""
        if options["check"]:
            self.check_database_size()

        if options["vacuum"]:
            self.vacuum_database()

        if options["clean_old"]:
            self.clean_old_data(days=options["days"])

        if not any([options["check"], options["vacuum"], options["clean_old"]]):
            self.stdout.write(
                self.style.WARNING("No action specified. Use --check, --vacuum, or --clean-old")
            )
            self.stdout.write("\nUsage:")
            self.stdout.write("  python manage.py db_cleanup --check")
            self.stdout.write("  python manage.py db_cleanup --vacuum")
            self.stdout.write("  python manage.py db_cleanup --clean-old --days=90")

    def check_database_size(self):
        """Check database and table sizes."""
        self.stdout.write(self.style.SUCCESS("\n=== Database Size Report ===\n"))

        with connection.cursor() as cursor:
            # Check if PostgreSQL
            if connection.vendor == "postgresql":
                # Total database size
                cursor.execute(
                    "SELECT pg_size_pretty(pg_database_size(current_database())) as size"
                )
                db_size = cursor.fetchone()[0]
                self.stdout.write(f"Total Database Size: {db_size}")

                # Table sizes
                cursor.execute("""
                    SELECT
                        schemaname || '.' || tablename AS table_name,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
                        pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
                    FROM pg_tables
                    WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                    LIMIT 15;
                """)

                self.stdout.write("\nTop 15 Largest Tables:")
                self.stdout.write("-" * 60)
                for table_name, size, _ in cursor.fetchall():
                    self.stdout.write(f"  {table_name:<50} {size:>10}")

                # Check WAL size
                cursor.execute("""
                    SELECT pg_size_pretty(
                        SUM(pg_stat_file('pg_wal/' || name)::json->>'size')::bigint
                    ) as wal_size
                    FROM pg_ls_waldir()
                """)
                try:
                    wal_size = cursor.fetchone()[0]
                    self.stdout.write(f"\nWAL (Write-Ahead Log) Size: {wal_size}")
                except Exception as e:
                    self.stdout.write(f"\nWAL size check failed: {e}")

            elif connection.vendor == "sqlite":
                # SQLite database size
                cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                size_bytes = cursor.fetchone()[0]
                size_mb = size_bytes / (1024 * 1024)
                self.stdout.write(f"Total Database Size: {size_mb:.2f} MB")

                # Table sizes for SQLite
                cursor.execute("""
                    SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = [row[0] for row in cursor.fetchall()]

                self.stdout.write("\nTable Row Counts:")
                self.stdout.write("-" * 60)
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    if count > 0:
                        self.stdout.write(f"  {table:<50} {count:>10} rows")

    def vacuum_database(self):
        """Run VACUUM to reclaim disk space (PostgreSQL only)."""
        if connection.vendor != "postgresql":
            self.stdout.write(
                self.style.WARNING("VACUUM is only available for PostgreSQL")
            )
            return

        self.stdout.write(self.style.SUCCESS("\n=== Running VACUUM ===\n"))

        with connection.cursor() as cursor:
            # VACUUM cannot run inside a transaction block
            old_autocommit = connection.autocommit
            connection.autocommit = True

            try:
                self.stdout.write("Running VACUUM ANALYZE...")
                cursor.execute("VACUUM ANALYZE")
                self.stdout.write(self.style.SUCCESS("✓ VACUUM completed successfully"))

                self.stdout.write("\nDisk space has been reclaimed.")
                self.stdout.write("Note: VACUUM FULL requires more time and locks tables.")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ VACUUM failed: {e}"))

            finally:
                connection.autocommit = old_autocommit

    def clean_old_data(self, days=90):
        """Clean old data to free up space."""
        self.stdout.write(
            self.style.WARNING(f"\n=== Cleaning data older than {days} days ===\n")
        )

        cutoff_date = timezone.now() - timedelta(days=days)

        # Import models here to avoid circular imports
        from books.models import TranslationJob, ChapterView
        from django_celery_beat.models import PeriodicTask
        from django.contrib.sessions.models import Session

        deleted_counts = {}

        # Clean failed translation jobs
        old_jobs = TranslationJob.objects.filter(
            created_at__lt=cutoff_date,
            status__in=["failed", "completed"]
        )
        count = old_jobs.count()
        if count > 0:
            self.stdout.write(f"Found {count} old translation jobs")
            confirm = input("Delete? (yes/no): ")
            if confirm.lower() == "yes":
                old_jobs.delete()
                deleted_counts["TranslationJob"] = count

        # Clean old chapter views (optional - be careful!)
        # old_views = ChapterView.objects.filter(viewed_at__lt=cutoff_date)
        # count = old_views.count()
        # if count > 0:
        #     self.stdout.write(f"Found {count} old chapter views")
        #     confirm = input("Delete? (yes/no): ")
        #     if confirm.lower() == "yes":
        #         old_views.delete()
        #         deleted_counts["ChapterView"] = count

        # Clean expired sessions
        Session.objects.filter(expire_date__lt=timezone.now()).delete()

        # Summary
        self.stdout.write("\n" + self.style.SUCCESS("=== Cleanup Summary ==="))
        for model, count in deleted_counts.items():
            self.stdout.write(f"  {model}: {count} records deleted")

        if not deleted_counts:
            self.stdout.write("  No data was deleted")

        self.stdout.write("\nRun --vacuum to reclaim disk space after cleanup.")
