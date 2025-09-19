"""
Django management command to test EntityExtractionService
Usage: python manage.py test_entity_extraction
"""

from django.core.management.base import BaseCommand
from translation.services import EntityExtractionService


class Command(BaseCommand):
    help = "Test the AI entity extraction service"

    def handle(self, *args, **options):
        # Sample Chinese web novel content
        sample_content = """
        李伟是天元宗的弟子，他在龙谷修炼已经三年了。
        今天，师父张明告诉他，他已经掌握了基础的气修炼法。
        明天他将前往玄武城参加年度的武者大会。
        李伟心中既兴奋又紧张，这是他第一次离开宗门。
        在玄武城，他将遇到来自其他宗门的强者，包括剑宗的天才弟子。
        """

        self.stdout.write("Testing EntityExtractionService...")
        self.stdout.write(f"Sample content: {sample_content[:100]}...")

        try:
            # Initialize service
            extractor = EntityExtractionService()
            self.stdout.write(self.style.SUCCESS("✓ EntityExtractionService initialized"))

            # Extract entities
            result = extractor.extract_entities_and_summary(sample_content, "zh")
            self.stdout.write(self.style.SUCCESS("✓ Entity extraction completed"))

            # Display results
            self.stdout.write("\n=== EXTRACTION RESULTS ===")
            self.stdout.write(f"Characters: {result['characters']}")
            self.stdout.write(f"Places: {result['places']}")
            self.stdout.write(f"Terms: {result['terms']}")
            self.stdout.write(f"Summary: {result['summary']}")

            # Validate structure
            required_keys = ["characters", "places", "terms", "summary"]
            missing_keys = [key for key in required_keys if key not in result]

            if missing_keys:
                self.stdout.write(self.style.ERROR(f"✗ Missing keys: {missing_keys}"))
                return

            self.stdout.write(self.style.SUCCESS("\n✓ All tests passed!"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Test failed: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())