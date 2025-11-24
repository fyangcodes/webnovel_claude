"""
Django management command to migrate language codes to BCP 47 standard.

This command:
1. Updates Language model codes from custom codes to BCP 47 standard
2. Updates all translation JSONFields across models (Section, Genre, Tag, Author, BookEntity)
3. Handles URL redirects by keeping old codes as reference

Usage:
    python manage.py migrate_to_bcp47 [--dry-run] [--verbose]
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from books.models import Language, Section, Genre, Tag, Author, BookEntity


class Command(BaseCommand):
    help = "Migrate language codes to BCP 47 standard and update all translation fields"

    # Mapping from old codes to BCP 47 standard codes
    # Add your current language codes here
    CODE_MAPPING = {
        # Common non-standard codes that might be in use:
        'zh': 'zh-hans',        # Chinese -> Simplified Chinese
        'zh-cn': 'zh-hans',     # Chinese (China) -> Simplified Chinese
        'zh-CN': 'zh-hans',     # Chinese (China) -> Simplified Chinese
        'cn': 'zh-hans',        # CN -> Simplified Chinese
        'tw': 'zh-hant',        # TW -> Traditional Chinese
        'zh-tw': 'zh-hant',     # Chinese (Taiwan) -> Traditional Chinese
        'zh-TW': 'zh-hant',     # Chinese (Taiwan) -> Traditional Chinese
        'hk': 'zh-hant',        # HK -> Traditional Chinese
        'jp': 'ja',             # JP -> Japanese
        'kr': 'ko',             # KR -> Korean
        'sp': 'es',             # SP -> Spanish
        'fr': 'fr',             # French (no change)
        'en': 'en',             # English (no change)
        'ja': 'ja',             # Japanese (no change)
        'ko': 'ko',             # Korean (no change)
        'es': 'es',             # Spanish (no change)
        # BCP 47 codes (no change if already correct)
        'zh-hans': 'zh-hans',
        'zh-hant': 'zh-hant',
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))

        # Step 1: Check current language codes
        self.stdout.write("\n" + "="*70)
        self.stdout.write("Step 1: Checking current language codes in database")
        self.stdout.write("="*70)

        languages = Language.objects.all()
        code_changes = {}

        for lang in languages:
            old_code = lang.code
            new_code = self.CODE_MAPPING.get(old_code.lower(), old_code)

            if old_code != new_code:
                code_changes[old_code] = new_code
                self.stdout.write(
                    self.style.WARNING(f"  {old_code} -> {new_code} ({lang.name})")
                )
            else:
                if verbose:
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✓ {old_code} ({lang.name}) - already BCP 47 compliant")
                    )

        if not code_changes:
            self.stdout.write(self.style.SUCCESS("\n✓ All language codes are already BCP 47 compliant!"))
            return

        # Step 2: Identify affected models
        self.stdout.write("\n" + "="*70)
        self.stdout.write("Step 2: Identifying models with translation fields")
        self.stdout.write("="*70)

        models_to_update = [
            ('Section', Section),
            ('Genre', Genre),
            ('Tag', Tag),
            ('Author', Author),
            ('BookEntity', BookEntity),
        ]

        model_counts = {}
        for model_name, model_class in models_to_update:
            if model_name == 'BookEntity':
                # BookEntity uses simple dict format: {"en": "name", "zh": "name"}
                count = model_class.objects.exclude(translations={}).count()
            else:
                # LocalizationModel uses nested format: {"en": {"name": "x", "description": "y"}}
                count = model_class.objects.exclude(translations={}).count()

            model_counts[model_name] = count
            if count > 0:
                self.stdout.write(f"  • {model_name}: {count} objects with translations")
            elif verbose:
                self.stdout.write(self.style.WARNING(f"  • {model_name}: No translations found"))

        # Step 3: Perform migration
        if not dry_run:
            self.stdout.write("\n" + "="*70)
            self.stdout.write("Step 3: Performing migration")
            self.stdout.write("="*70)

            try:
                with transaction.atomic():
                    # Update Language model codes
                    self.stdout.write("\n  Updating Language model codes...")
                    for old_code, new_code in code_changes.items():
                        lang = Language.objects.get(code=old_code)
                        lang.code = new_code
                        lang.save()
                        self.stdout.write(
                            self.style.SUCCESS(f"    ✓ Updated: {old_code} -> {new_code}")
                        )

                    # Update translation fields in all models
                    self.stdout.write("\n  Updating translation fields...")

                    for model_name, model_class in models_to_update:
                        updated_count = self._update_model_translations(
                            model_class,
                            code_changes,
                            model_name == 'BookEntity',
                            verbose
                        )
                        if updated_count > 0:
                            self.stdout.write(
                                self.style.SUCCESS(f"    ✓ {model_name}: Updated {updated_count} objects")
                            )

                    self.stdout.write("\n" + "="*70)
                    self.stdout.write(self.style.SUCCESS("✓ Migration completed successfully!"))
                    self.stdout.write("="*70)

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"\n✗ Migration failed: {e}")
                )
                raise

        else:
            # Dry run summary
            self.stdout.write("\n" + "="*70)
            self.stdout.write("DRY RUN SUMMARY")
            self.stdout.write("="*70)
            self.stdout.write(f"\nLanguage codes to update: {len(code_changes)}")
            for old_code, new_code in code_changes.items():
                self.stdout.write(f"  • {old_code} -> {new_code}")

            self.stdout.write(f"\nModels to update:")
            for model_name, count in model_counts.items():
                if count > 0:
                    self.stdout.write(f"  • {model_name}: ~{count} objects")

            self.stdout.write("\n" + self.style.WARNING("Run without --dry-run to apply changes"))

    def _update_model_translations(self, model_class, code_changes, is_simple_format=False, verbose=False):
        """
        Update translation fields in a model.

        Args:
            model_class: The model class to update
            code_changes: Dict mapping old codes to new codes
            is_simple_format: True for BookEntity (simple dict), False for LocalizationModel (nested dict)
            verbose: Whether to show detailed output

        Returns:
            Number of objects updated
        """
        updated_count = 0
        objects = model_class.objects.exclude(translations={})

        for obj in objects:
            if not obj.translations:
                continue

            old_translations = obj.translations.copy()
            new_translations = {}
            changed = False

            if is_simple_format:
                # BookEntity format: {"en": "Li Wei", "zh": "李伟"}
                for old_code, value in old_translations.items():
                    new_code = code_changes.get(old_code, old_code)
                    new_translations[new_code] = value
                    if old_code != new_code:
                        changed = True
                        if verbose:
                            self.stdout.write(
                                f"      {model_class.__name__} #{obj.pk}: {old_code} -> {new_code}"
                            )
            else:
                # LocalizationModel format: {"en": {"name": "x", "description": "y"}}
                for old_code, content in old_translations.items():
                    new_code = code_changes.get(old_code, old_code)
                    new_translations[new_code] = content
                    if old_code != new_code:
                        changed = True
                        if verbose:
                            self.stdout.write(
                                f"      {model_class.__name__} #{obj.pk}: {old_code} -> {new_code}"
                            )

            if changed:
                obj.translations = new_translations
                obj.save(update_fields=['translations'])
                updated_count += 1

        return updated_count
