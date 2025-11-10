"""
Management command to generate analytics reports.
"""

from django.core.management.base import BaseCommand
from books.analytics import Analytics
from books.models import Book, Language
from tabulate import tabulate


class Command(BaseCommand):
    help = "Generate analytics reports for books and chapters"

    def add_arguments(self, parser):
        parser.add_argument(
            "--language",
            type=str,
            default="en",
            help="Language code to filter by (default: en)",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Number of days to analyze (default: 7)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Number of results to show (default: 10)",
        )
        parser.add_argument(
            "--report",
            type=str,
            choices=["trending", "genres", "hours", "all"],
            default="all",
            help="Type of report to generate",
        )

    def handle(self, *args, **options):
        lang_code = options["language"]
        days = options["days"]
        limit = options["limit"]
        report_type = options["report"]

        # Validate language
        try:
            language = Language.objects.get(code=lang_code)
        except Language.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Language '{lang_code}' not found")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"\n📊 Analytics Report for {language.name} (last {days} days)\n"
            )
        )

        # Trending Books
        if report_type in ["trending", "all"]:
            self.print_trending_books(language, days, limit)

        # Popular Genres
        if report_type in ["genres", "all"]:
            self.print_popular_genres(language, days, limit)

        # Reading Hours
        if report_type in ["hours", "all"]:
            self.print_reading_hours(days)

    def print_trending_books(self, language, days, limit):
        """Print trending books report"""
        self.stdout.write(self.style.WARNING(f"\n📈 Trending Books (Top {limit})"))
        self.stdout.write("=" * 80 + "\n")

        trending = Analytics.get_trending_books(language, days=days, limit=limit)

        if not trending:
            self.stdout.write(self.style.WARNING("No trending books found\n"))
            return

        data = []
        for i, book in enumerate(trending, 1):
            stats = getattr(book, "stats", None)
            views = stats.total_views if stats else 0
            unique_7d = stats.unique_readers_7d if stats else 0

            data.append(
                [
                    i,
                    book.title[:40],
                    book.author[:20] if book.author else "-",
                    views,
                    unique_7d,
                    book.progress,
                ]
            )

        headers = ["#", "Title", "Author", "Total Views", f"Unique ({days}d)", "Status"]
        self.stdout.write(
            tabulate(data, headers=headers, tablefmt="grid") + "\n"
        )

    def print_popular_genres(self, language, days, limit):
        """Print popular genres report"""
        self.stdout.write(self.style.WARNING(f"\n🏷️  Popular Genres (Top {limit})"))
        self.stdout.write("=" * 80 + "\n")

        genres = Analytics.get_popular_genres(language, days=days, limit=limit)

        if not genres:
            self.stdout.write(self.style.WARNING("No genre data available\n"))
            return

        data = [[i, g["genre"], g["views"]] for i, g in enumerate(genres, 1)]

        headers = ["#", "Genre", "Views"]
        self.stdout.write(tabulate(data, headers=headers, tablefmt="grid") + "\n")

    def print_reading_hours(self, days):
        """Print reading hours distribution"""
        self.stdout.write(self.style.WARNING(f"\n🕐 Popular Reading Hours"))
        self.stdout.write("=" * 80 + "\n")

        hours = Analytics.get_popular_reading_hours(days=days)

        if not hours:
            self.stdout.write(self.style.WARNING("No reading hour data available\n"))
            return

        # Sort by view count to show peak hours
        sorted_hours = sorted(hours, key=lambda x: x["view_count"], reverse=True)[:10]

        data = [
            [f"{h['hour']:02d}:00", h["view_count"], self._make_bar(h["view_count"], max(h["view_count"] for h in sorted_hours))]
            for h in sorted_hours
        ]

        headers = ["Hour", "Views", "Distribution"]
        self.stdout.write(tabulate(data, headers=headers, tablefmt="grid") + "\n")

    def _make_bar(self, value, max_value):
        """Create a simple ASCII bar chart"""
        if max_value == 0:
            return ""
        bar_length = int((value / max_value) * 30)
        return "█" * bar_length
