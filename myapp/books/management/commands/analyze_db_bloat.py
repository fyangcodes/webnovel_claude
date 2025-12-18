"""
Analyze database bloat and identify space usage issues.

Usage:
    python manage.py analyze_db_bloat
"""

import logging
from django.core.management.base import BaseCommand
from django.db import connection

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Analyze database for bloat and unusual space usage"

    def handle(self, *args, **options):
        """Analyze database space usage."""

        if connection.vendor != "postgresql":
            self.stdout.write(
                self.style.WARNING("This command is designed for PostgreSQL")
            )
            return

        self.stdout.write(self.style.SUCCESS("\n=== Database Bloat Analysis ===\n"))

        with connection.cursor() as cursor:
            # 1. Check total database size
            cursor.execute("""
                SELECT pg_size_pretty(pg_database_size(current_database())) as size,
                       pg_database_size(current_database()) as size_bytes
            """)
            db_size, db_size_bytes = cursor.fetchone()
            self.stdout.write(f"Total Database Size: {db_size} ({db_size_bytes:,} bytes)\n")

            # 2. Table sizes with bloat estimation
            self.stdout.write(self.style.SUCCESS("=== Table Sizes (including indexes) ===\n"))
            cursor.execute("""
                SELECT
                    schemaname || '.' || tablename AS table_name,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
                    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) -
                                   pg_relation_size(schemaname||'.'||tablename)) AS indexes_size,
                    pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
                FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT 20;
            """)

            self.stdout.write(f"{'Table':<50} {'Total':>12} {'Table Only':>12} {'Indexes':>12}")
            self.stdout.write("-" * 90)

            total_size = 0
            for table_name, total, table_only, indexes, size_bytes in cursor.fetchall():
                self.stdout.write(f"{table_name:<50} {total:>12} {table_only:>12} {indexes:>12}")
                total_size += size_bytes

            # 3. Index sizes
            self.stdout.write(self.style.SUCCESS("\n=== Largest Indexes ===\n"))
            cursor.execute("""
                SELECT
                    schemaname || '.' || tablename AS table_name,
                    indexname,
                    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
                    pg_relation_size(indexrelid) AS size_bytes
                FROM pg_indexes
                JOIN pg_class ON indexrelid = pg_class.oid
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY pg_relation_size(indexrelid) DESC
                LIMIT 15;
            """)

            self.stdout.write(f"{'Table':<40} {'Index':<40} {'Size':>12}")
            self.stdout.write("-" * 95)

            for table_name, index_name, size, _ in cursor.fetchall():
                self.stdout.write(f"{table_name:<40} {index_name:<40} {size:>12}")

            # 4. Dead tuples (bloat indicator)
            self.stdout.write(self.style.SUCCESS("\n=== Dead Tuples (Bloat Indicators) ===\n"))
            cursor.execute("""
                SELECT
                    schemaname || '.' || relname AS table_name,
                    n_live_tup AS live_tuples,
                    n_dead_tup AS dead_tuples,
                    CASE WHEN n_live_tup > 0
                         THEN round(100.0 * n_dead_tup / (n_live_tup + n_dead_tup), 2)
                         ELSE 0
                    END AS dead_percentage,
                    last_vacuum,
                    last_autovacuum
                FROM pg_stat_user_tables
                WHERE n_dead_tup > 0
                ORDER BY n_dead_tup DESC
                LIMIT 15;
            """)

            self.stdout.write(f"{'Table':<50} {'Live':>10} {'Dead':>10} {'Dead %':>8} {'Last Vacuum':<20}")
            self.stdout.write("-" * 105)

            has_bloat = False
            for table_name, live, dead, pct, last_vac, last_auto in cursor.fetchall():
                has_bloat = True
                last_vac_str = str(last_vac or last_auto or "Never")[:19]
                style = self.style.ERROR if pct > 20 else self.style.WARNING
                self.stdout.write(
                    style(f"{table_name:<50} {live:>10} {dead:>10} {pct:>7}% {last_vac_str:<20}")
                )

            if has_bloat:
                self.stdout.write("\n" + self.style.WARNING(
                    "⚠️  High dead tuple percentage indicates bloat. Run VACUUM to reclaim space."
                ))

            # 5. Row counts vs size (detect inefficient storage)
            self.stdout.write(self.style.SUCCESS("\n=== Row Counts vs Storage ===\n"))
            cursor.execute("""
                SELECT
                    schemaname || '.' || tablename AS table_name,
                    n_live_tup AS row_count,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
                    pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes,
                    CASE WHEN n_live_tup > 0
                         THEN pg_total_relation_size(schemaname||'.'||tablename) / n_live_tup
                         ELSE 0
                    END AS bytes_per_row
                FROM pg_stat_user_tables
                JOIN pg_tables USING (schemaname, tablename)
                WHERE n_live_tup > 0
                ORDER BY bytes_per_row DESC
                LIMIT 15;
            """)

            self.stdout.write(f"{'Table':<50} {'Rows':>10} {'Size':>12} {'Bytes/Row':>12}")
            self.stdout.write("-" * 90)

            for table_name, rows, size, _, bytes_per_row in cursor.fetchall():
                # Flag tables with >10KB per row as potentially inefficient
                style = self.style.ERROR if bytes_per_row > 10240 else (
                    self.style.WARNING if bytes_per_row > 5120 else self.style.SUCCESS
                )
                self.stdout.write(
                    style(f"{table_name:<50} {rows:>10} {size:>12} {bytes_per_row:>12,}")
                )

            # 6. WAL (Write-Ahead Log) size
            self.stdout.write(self.style.SUCCESS("\n=== WAL (Write-Ahead Log) Size ===\n"))
            try:
                cursor.execute("""
                    SELECT
                        count(*) as wal_files,
                        pg_size_pretty(sum((pg_stat_file('pg_wal/' || name)).size)::bigint) as total_size
                    FROM pg_ls_waldir()
                """)
                wal_files, wal_size = cursor.fetchone()
                self.stdout.write(f"WAL Files: {wal_files}")
                self.stdout.write(f"WAL Size: {wal_size}")

                if wal_files > 100:
                    self.stdout.write(
                        self.style.ERROR(f"⚠️  High WAL file count ({wal_files}). This may indicate checkpoint issues.")
                    )
            except Exception as e:
                self.stdout.write(f"Could not check WAL size: {e}")

            # 7. TOAST tables (for large text/binary data)
            self.stdout.write(self.style.SUCCESS("\n=== TOAST Tables (Large Data Storage) ===\n"))
            cursor.execute("""
                SELECT
                    n.nspname || '.' || c.relname AS table_name,
                    n.nspname || '.' || t.relname AS toast_table,
                    pg_size_pretty(pg_total_relation_size(t.oid)) AS toast_size,
                    pg_total_relation_size(t.oid) AS size_bytes
                FROM pg_class c
                JOIN pg_class t ON c.reltoastrelid = t.oid
                JOIN pg_namespace n ON c.relnamespace = n.oid
                WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
                  AND pg_total_relation_size(t.oid) > 0
                ORDER BY pg_total_relation_size(t.oid) DESC
                LIMIT 10;
            """)

            toast_results = cursor.fetchall()
            if toast_results:
                self.stdout.write(f"{'Table':<50} {'TOAST Table':<50} {'Size':>12}")
                self.stdout.write("-" * 115)

                for table_name, toast_table, size, _ in toast_results:
                    self.stdout.write(f"{table_name:<50} {toast_table:<50} {size:>12}")

                self.stdout.write("\n" + self.style.WARNING(
                    "TOAST tables store large text/binary data. Large TOAST tables are normal for text-heavy data."
                ))
            else:
                self.stdout.write("No significant TOAST table usage.")

            # 8. Recommendations
            self.stdout.write(self.style.SUCCESS("\n=== Recommendations ===\n"))

            recommendations = []

            # Check if VACUUM is needed
            cursor.execute("""
                SELECT COUNT(*) FROM pg_stat_user_tables
                WHERE n_dead_tup > 1000 OR (n_dead_tup::float / NULLIF(n_live_tup, 0) > 0.2)
            """)
            bloated_tables = cursor.fetchone()[0]
            if bloated_tables > 0:
                recommendations.append(
                    f"🔧 Run VACUUM: {bloated_tables} tables have significant dead tuples"
                )

            # Check for large indexes
            cursor.execute("""
                SELECT COUNT(*) FROM pg_indexes
                JOIN pg_class ON indexrelid = pg_class.oid
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                  AND pg_relation_size(indexrelid) > 10485760  -- 10MB
            """)
            large_indexes = cursor.fetchone()[0]
            if large_indexes > 5:
                recommendations.append(
                    f"📊 Review indexes: {large_indexes} indexes are larger than 10MB"
                )

            # Check bytes per row
            cursor.execute("""
                SELECT tablename,
                       pg_total_relation_size(schemaname||'.'||tablename) / NULLIF(n_live_tup, 0) as bpr
                FROM pg_stat_user_tables
                JOIN pg_tables USING (schemaname, tablename)
                WHERE n_live_tup > 0
                ORDER BY bpr DESC
                LIMIT 1
            """)
            result = cursor.fetchone()
            if result and result[1] > 10240:
                recommendations.append(
                    f"⚠️  Table '{result[0]}' uses {result[1]:,} bytes/row (very high!)"
                )

            if not recommendations:
                recommendations.append("✅ Database looks healthy!")

            for rec in recommendations:
                self.stdout.write(f"  {rec}")

            self.stdout.write("\n" + self.style.SUCCESS("=== Analysis Complete ===\n"))
