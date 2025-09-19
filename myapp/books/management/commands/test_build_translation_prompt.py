from django.core.management.base import BaseCommand
from books.models import Chapter, Language
from translation.services import TranslationService


class Command(BaseCommand):
    help = "Test the translation prompt building for a specific chapter"

    def add_arguments(self, parser):
        parser.add_argument(
            "--chapter-id",
            type=int,
            default=206,
            help="Chapter ID to test (default: 206)",
        )
        parser.add_argument(
            "--target-lang",
            type=str,
            default="en",
            help="Target language code (default: en)",
        )

    def handle(self, *args, **options):
        chapter_id = options["chapter_id"]
        target_lang_code = options["target_lang"]

        try:
            # Get the chapter
            chapter = Chapter.objects.get(id=chapter_id)
            self.stdout.write(f"Found chapter: {chapter.title}")

            # Get target language
            target_language = Language.objects.get(code=target_lang_code)
            self.stdout.write(f"Target language: {target_language.name}")

            # Create translation service and build prompt
            service = TranslationService()
            prompt = service._build_translation_prompt(chapter, target_language)

            # Output the prompt
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write("GENERATED TRANSLATION PROMPT:")
            self.stdout.write("=" * 80)
            self.stdout.write(prompt)
            self.stdout.write("=" * 80)

        except Chapter.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Chapter with ID {chapter_id} does not exist")
            )
        except Language.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Language "{target_lang_code}" does not exist')
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
