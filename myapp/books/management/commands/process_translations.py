from django.core.management.base import BaseCommand
from translation.services import process_translation_jobs


class Command(BaseCommand):
    help = "Process pending translation jobs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-jobs",
            type=int,
            default=50,
            help="Maximum number of jobs to process in one run",
        )

    def handle(self, *args, **options):
        max_jobs = options["max_jobs"]
        self.stdout.write(f"Processing up to {max_jobs} translation jobs...")

        try:
            process_translation_jobs(max_jobs)
            self.stdout.write(
                self.style.SUCCESS("Translation job processing completed")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error processing translation jobs: {e}")
            )
            raise
