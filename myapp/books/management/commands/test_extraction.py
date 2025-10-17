from django.core.management.base import BaseCommand, CommandError
from books.models import Chapter
from translation.services import EntityExtractionService


class Command(BaseCommand):
    help = "Test entity extraction on a chapter or sample text"

    def add_arguments(self, parser):
        parser.add_argument(
            "--chapter-id", type=int, help="Chapter ID to test extraction on"
        )
        parser.add_argument(
            "--use-sample",
            action="store_true",
            help="Use sample text instead of a chapter",
        )

    def handle(self, **options):
        if options["chapter_id"]:
            self.test_chapter_extraction(options["chapter_id"])
        elif options["use_sample"]:
            self.test_sample_extraction()
        else:
            self.stdout.write(
                self.style.ERROR("Please provide either --chapter-id or --use-sample")
            )

    def test_chapter_extraction(self, chapter_id):
        """Test extraction on a specific chapter"""
        try:
            chapter = Chapter.objects.get(id=chapter_id)
        except Chapter.DoesNotExist:
            raise CommandError(f"Chapter with ID {chapter_id} does not exist")

        self.stdout.write(
            self.style.SUCCESS(
                f'Testing extraction on Chapter {chapter_id}: "{chapter.title}"'
            )
        )
        self.stdout.write(f"Content length: {len(chapter.content)} characters")
        self.stdout.write(f"Language: {chapter.book.language.name}")
        self.stdout.write("-" * 60)

        # Test the extraction service
        service = EntityExtractionService()

        # Show the prompt that will be used
        prompt = service._build_extraction_prompt(
            chapter.content, chapter.book.language.code
        )

        self.stdout.write(self.style.WARNING("Generated Prompt:"))
        self.stdout.write("=" * 60)
        self.stdout.write(prompt)
        self.stdout.write("=" * 60)

        # Perform actual extraction
        try:
            result = service.extract_entities_and_summary(
                chapter.content, chapter.book.language.code
            )

            self.stdout.write(self.style.SUCCESS("\nExtraction Results:"))
            self.stdout.write(f"Characters: {result.get('characters', [])}")
            self.stdout.write(f"Places: {result.get('places', [])}")
            self.stdout.write(f"Terms: {result.get('terms', [])}")
            self.stdout.write(f"Summary: {result.get('summary', '')}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Extraction failed: {e}"))

    def test_sample_extraction(self):
        """Test extraction on sample text"""
        sample_content = """
        She walked to the elevator on the 15th floor. The manager sat on the sofa near the WC.
        Shanghai was busy today. He called from his phone. The 17th stock market was rising.
        But there was also Master Zhang, the legendary Phoenix Sect, and the mystical
        Jade Cultivation Technique that only the Azure Dragon Palace possessed.
        The Crimson Flame Sect had been searching for the Ancient Void Scripture for centuries.
        """

        self.stdout.write(self.style.SUCCESS("Testing extraction on sample text"))
        self.stdout.write("-" * 60)

        service = EntityExtractionService()

        # Show the prompt
        prompt = service._build_extraction_prompt(sample_content, "en")

        self.stdout.write(self.style.WARNING("Generated Prompt:"))
        self.stdout.write("=" * 60)
        self.stdout.write(prompt)
        self.stdout.write("=" * 60)

        # Expected vs actual
        self.stdout.write(self.style.WARNING("\nExpected behavior:"))
        self.stdout.write(
            "Should NOT extract: she, elevator, 15th, manager, sofa, WC, Shanghai, phone, 17th"
        )
        self.stdout.write(
            "Should extract: Master Zhang, Phoenix Sect, Jade Cultivation Technique, Azure Dragon Palace, Crimson Flame Sect, Ancient Void Scripture"
        )

        # Perform extraction (if AI service is available)
        try:
            result = service.extract_entities_and_summary(sample_content, "en")

            self.stdout.write(self.style.SUCCESS("\nActual Extraction Results:"))
            self.stdout.write(f"Characters: {result.get('characters', [])}")
            self.stdout.write(f"Places: {result.get('places', [])}")
            self.stdout.write(f"Terms: {result.get('terms', [])}")
            self.stdout.write(f"Summary: {result.get('summary', '')}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Extraction failed: {e}"))
            self.stdout.write("(This is expected if OpenAI API is not configured)")
