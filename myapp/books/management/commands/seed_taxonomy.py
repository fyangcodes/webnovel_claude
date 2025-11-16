"""
Management command to seed taxonomy test data.

Creates comprehensive test data for sections, genres, tags, and sample books.
Safe to run multiple times (idempotent).

Usage:
    python manage.py seed_taxonomy [--clear]

Options:
    --clear: Clear existing taxonomy data before seeding (WARNING: destructive)
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from books.models import (
    Section, Genre, Tag, BookMaster, Book, BookGenre, BookTag,
    Language
)
from accounts.models import User


class Command(BaseCommand):
    help = 'Seed taxonomy test data (sections, genres, tags, sample books)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing taxonomy data before seeding (WARNING: destructive)',
        )

    def handle(self, *args, **options):
        """Execute the seeding operation"""
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing existing taxonomy data...'))
            self.clear_data()

        self.stdout.write(self.style.SUCCESS('Starting taxonomy data seeding...'))

        try:
            with transaction.atomic():
                # Seed in order of dependencies
                self.seed_sections()
                self.seed_genres()
                self.seed_tags()
                self.seed_sample_books()

            self.stdout.write(self.style.SUCCESS('Successfully seeded taxonomy data!'))
            self.print_summary()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error seeding data: {str(e)}'))
            raise

    def clear_data(self):
        """Clear existing taxonomy data (destructive)"""
        BookTag.objects.all().delete()
        BookGenre.objects.all().delete()
        Tag.objects.all().delete()
        Genre.objects.all().delete()
        Section.objects.all().delete()
        self.stdout.write(self.style.WARNING('Cleared all taxonomy data'))

    def seed_sections(self):
        """Create sections"""
        sections_data = [
            {
                'name': 'Fiction',
                'slug': 'fiction',
                'order': 1,
                'translations': {
                    'zh': {'name': '小说'},
                    'es': {'name': 'Ficción'},
                    'fr': {'name': 'Fiction'},
                }
            },
            {
                'name': 'BL',
                'slug': 'bl',
                'order': 2,
                'translations': {
                    'zh': {'name': '耽美'},
                    'es': {'name': 'BL'},
                    'fr': {'name': 'BL'},
                }
            },
            {
                'name': 'GL',
                'slug': 'gl',
                'order': 3,
                'translations': {
                    'zh': {'name': '百合'},
                    'es': {'name': 'GL'},
                    'fr': {'name': 'GL'},
                }
            },
            {
                'name': 'Non-Fiction',
                'slug': 'non-fiction',
                'order': 4,
                'translations': {
                    'zh': {'name': '非虚构'},
                    'es': {'name': 'No Ficción'},
                    'fr': {'name': 'Non-Fiction'},
                }
            },
        ]

        for data in sections_data:
            section, created = Section.objects.get_or_create(
                slug=data['slug'],
                defaults={
                    'name': data['name'],
                    'order': data['order'],
                    'translations': data['translations']
                }
            )
            if created:
                self.stdout.write(f'  Created section: {section.name}')
            else:
                self.stdout.write(f'  Section exists: {section.name}')

    def seed_genres(self):
        """Create genres with hierarchical structure"""
        # Get sections
        fiction = Section.objects.get(slug='fiction')
        bl = Section.objects.get(slug='bl')
        gl = Section.objects.get(slug='gl')
        non_fiction = Section.objects.get(slug='non-fiction')

        genres_data = [
            # Fiction Section
            {
                'name': 'Fantasy',
                'slug': 'fantasy',
                'section': fiction,
                'is_primary': True,
                'order': 1,
                'color': '#9333ea',
                'icon': 'fa-wand-magic-sparkles',
                'translations': {'zh': {'name': '奇幻'}, 'es': {'name': 'Fantasía'}, 'fr': {'name': 'Fantaisie'}}
            },
            {
                'name': 'Epic Fantasy',
                'slug': 'epic-fantasy',
                'section': fiction,
                'parent_slug': 'fantasy',
                'is_primary': False,
                'order': 1,
                'translations': {'zh': {'name': '史诗奇幻'}, 'es': {'name': 'Fantasía Épica'}, 'fr': {'name': 'Fantaisie Épique'}}
            },
            {
                'name': 'Urban Fantasy',
                'slug': 'urban-fantasy',
                'section': fiction,
                'parent_slug': 'fantasy',
                'is_primary': False,
                'order': 2,
                'translations': {'zh': {'name': '都市奇幻'}, 'es': {'name': 'Fantasía Urbana'}, 'fr': {'name': 'Fantaisie Urbaine'}}
            },
            {
                'name': 'Cultivation',
                'slug': 'cultivation',
                'section': fiction,
                'is_primary': True,
                'order': 2,
                'color': '#ea580c',
                'icon': 'fa-yin-yang',
                'translations': {'zh': {'name': '修真'}, 'es': {'name': 'Cultivación'}, 'fr': {'name': 'Cultivation'}}
            },
            {
                'name': 'Xianxia',
                'slug': 'xianxia',
                'section': fiction,
                'parent_slug': 'cultivation',
                'is_primary': False,
                'order': 1,
                'translations': {'zh': {'name': '仙侠'}, 'es': {'name': 'Xianxia'}, 'fr': {'name': 'Xianxia'}}
            },
            {
                'name': 'Wuxia',
                'slug': 'wuxia',
                'section': fiction,
                'parent_slug': 'cultivation',
                'is_primary': False,
                'order': 2,
                'translations': {'zh': {'name': '武侠'}, 'es': {'name': 'Wuxia'}, 'fr': {'name': 'Wuxia'}}
            },
            {
                'name': 'Romance',
                'slug': 'romance',
                'section': fiction,
                'is_primary': True,
                'order': 3,
                'color': '#ec4899',
                'icon': 'fa-heart',
                'translations': {'zh': {'name': '言情'}, 'es': {'name': 'Romance'}, 'fr': {'name': 'Romance'}}
            },
            {
                'name': 'Contemporary Romance',
                'slug': 'contemporary-romance',
                'section': fiction,
                'parent_slug': 'romance',
                'is_primary': False,
                'order': 1,
                'translations': {'zh': {'name': '现代言情'}, 'es': {'name': 'Romance Contemporáneo'}, 'fr': {'name': 'Romance Contemporain'}}
            },
            {
                'name': 'Sci-Fi',
                'slug': 'sci-fi',
                'section': fiction,
                'is_primary': True,
                'order': 4,
                'color': '#3b82f6',
                'icon': 'fa-rocket',
                'translations': {'zh': {'name': '科幻'}, 'es': {'name': 'Ciencia Ficción'}, 'fr': {'name': 'Science-Fiction'}}
            },
            {
                'name': 'Space Opera',
                'slug': 'space-opera',
                'section': fiction,
                'parent_slug': 'sci-fi',
                'is_primary': False,
                'order': 1,
                'translations': {'zh': {'name': '太空歌剧'}, 'es': {'name': 'Ópera Espacial'}, 'fr': {'name': 'Opéra Spatial'}}
            },

            # BL Section
            {
                'name': 'BL Fantasy',
                'slug': 'bl-fantasy',
                'section': bl,
                'is_primary': True,
                'order': 1,
                'color': '#9333ea',
                'icon': 'fa-wand-magic-sparkles',
                'translations': {'zh': {'name': '耽美奇幻'}, 'es': {'name': 'BL Fantasía'}, 'fr': {'name': 'BL Fantaisie'}}
            },
            {
                'name': 'BL Cultivation',
                'slug': 'bl-cultivation',
                'section': bl,
                'is_primary': True,
                'order': 2,
                'color': '#ea580c',
                'icon': 'fa-yin-yang',
                'translations': {'zh': {'name': '耽美修真'}, 'es': {'name': 'BL Cultivación'}, 'fr': {'name': 'BL Cultivation'}}
            },
            {
                'name': 'BL Modern',
                'slug': 'bl-modern',
                'section': bl,
                'is_primary': True,
                'order': 3,
                'color': '#06b6d4',
                'icon': 'fa-city',
                'translations': {'zh': {'name': '现代耽美'}, 'es': {'name': 'BL Moderno'}, 'fr': {'name': 'BL Moderne'}}
            },
            {
                'name': 'Office Romance',
                'slug': 'bl-office-romance',
                'section': bl,
                'parent_slug': 'bl-modern',
                'is_primary': False,
                'order': 1,
                'translations': {'zh': {'name': '职场耽美'}, 'es': {'name': 'Romance de Oficina'}, 'fr': {'name': 'Romance de Bureau'}}
            },

            # GL Section
            {
                'name': 'GL Fantasy',
                'slug': 'gl-fantasy',
                'section': gl,
                'is_primary': True,
                'order': 1,
                'color': '#9333ea',
                'icon': 'fa-wand-magic-sparkles',
                'translations': {'zh': {'name': '百合奇幻'}, 'es': {'name': 'GL Fantasía'}, 'fr': {'name': 'GL Fantaisie'}}
            },
            {
                'name': 'GL Modern',
                'slug': 'gl-modern',
                'section': gl,
                'is_primary': True,
                'order': 2,
                'color': '#06b6d4',
                'icon': 'fa-city',
                'translations': {'zh': {'name': '现代百合'}, 'es': {'name': 'GL Moderno'}, 'fr': {'name': 'GL Moderne'}}
            },
            {
                'name': 'Campus GL',
                'slug': 'gl-campus',
                'section': gl,
                'parent_slug': 'gl-modern',
                'is_primary': False,
                'order': 1,
                'translations': {'zh': {'name': '校园百合'}, 'es': {'name': 'GL Escolar'}, 'fr': {'name': 'GL Campus'}}
            },

            # Non-Fiction Section
            {
                'name': 'Biography',
                'slug': 'biography',
                'section': non_fiction,
                'is_primary': True,
                'order': 1,
                'color': '#059669',
                'icon': 'fa-user',
                'translations': {'zh': {'name': '传记'}, 'es': {'name': 'Biografía'}, 'fr': {'name': 'Biographie'}}
            },
            {
                'name': 'History',
                'slug': 'history',
                'section': non_fiction,
                'is_primary': True,
                'order': 2,
                'color': '#d97706',
                'icon': 'fa-landmark',
                'translations': {'zh': {'name': '历史'}, 'es': {'name': 'Historia'}, 'fr': {'name': 'Histoire'}}
            },
        ]

        # Create primary genres first
        for data in genres_data:
            if data.get('is_primary', True):
                genre, created = Genre.objects.get_or_create(
                    section=data['section'],
                    slug=data['slug'],
                    defaults={
                        'name': data['name'],
                        'is_primary': data['is_primary'],
                        'color': data.get('color', ''),
                        'icon': data.get('icon', ''),
                        'translations': data.get('translations', {})
                    }
                )
                if created:
                    self.stdout.write(f'  Created primary genre: {genre.name}')
                else:
                    self.stdout.write(f'  Genre exists: {genre.name}')

        # Create sub-genres (with parent references)
        for data in genres_data:
            if not data.get('is_primary', True):
                parent = Genre.objects.get(section=data['section'], slug=data['parent_slug'])
                genre, created = Genre.objects.get_or_create(
                    section=data['section'],
                    slug=data['slug'],
                    defaults={
                        'name': data['name'],
                        'parent': parent,
                        'is_primary': data['is_primary'],
                        'translations': data.get('translations', {})
                    }
                )
                if created:
                    self.stdout.write(f'  Created sub-genre: {genre.name} (parent: {parent.name})')
                else:
                    self.stdout.write(f'  Sub-genre exists: {genre.name}')

    def seed_tags(self):
        """Create tags organized by category"""
        tags_data = [
            # Protagonist tags
            {'name': 'Strong Protagonist', 'slug': 'strong-protagonist', 'category': 'protagonist',
             'translations': {'zh': {'name': '强大主角'}, 'es': {'name': 'Protagonista Fuerte'}, 'fr': {'name': 'Protagoniste Fort'}}},
            {'name': 'Smart Protagonist', 'slug': 'smart-protagonist', 'category': 'protagonist',
             'translations': {'zh': {'name': '聪明主角'}, 'es': {'name': 'Protagonista Inteligente'}, 'fr': {'name': 'Protagoniste Intelligent'}}},
            {'name': 'System User', 'slug': 'system-user', 'category': 'protagonist',
             'translations': {'zh': {'name': '系统流'}, 'es': {'name': 'Usuario de Sistema'}, 'fr': {'name': 'Utilisateur de Système'}}},
            {'name': 'Transmigration', 'slug': 'transmigration', 'category': 'protagonist',
             'translations': {'zh': {'name': '穿越'}, 'es': {'name': 'Transmigración'}, 'fr': {'name': 'Transmigration'}}},

            # Setting tags
            {'name': 'Ancient China', 'slug': 'ancient-china', 'category': 'setting',
             'translations': {'zh': {'name': '古代中国'}, 'es': {'name': 'China Antigua'}, 'fr': {'name': 'Chine Ancienne'}}},
            {'name': 'Modern World', 'slug': 'modern-world', 'category': 'setting',
             'translations': {'zh': {'name': '现代世界'}, 'es': {'name': 'Mundo Moderno'}, 'fr': {'name': 'Monde Moderne'}}},
            {'name': 'Fantasy World', 'slug': 'fantasy-world', 'category': 'setting',
             'translations': {'zh': {'name': '奇幻世界'}, 'es': {'name': 'Mundo Fantástico'}, 'fr': {'name': 'Monde Fantastique'}}},
            {'name': 'Academy', 'slug': 'academy', 'category': 'setting',
             'translations': {'zh': {'name': '学院'}, 'es': {'name': 'Academia'}, 'fr': {'name': 'Académie'}}},

            # Plot tags
            {'name': 'Revenge', 'slug': 'revenge', 'category': 'plot',
             'translations': {'zh': {'name': '复仇'}, 'es': {'name': 'Venganza'}, 'fr': {'name': 'Vengeance'}}},
            {'name': 'Power Struggle', 'slug': 'power-struggle', 'category': 'plot',
             'translations': {'zh': {'name': '权力斗争'}, 'es': {'name': 'Lucha de Poder'}, 'fr': {'name': 'Lutte de Pouvoir'}}},
            {'name': 'Mystery', 'slug': 'mystery', 'category': 'plot',
             'translations': {'zh': {'name': '悬疑'}, 'es': {'name': 'Misterio'}, 'fr': {'name': 'Mystère'}}},

            # Relationship tags
            {'name': 'Enemies to Lovers', 'slug': 'enemies-to-lovers', 'category': 'relationship',
             'translations': {'zh': {'name': '欢喜冤家'}, 'es': {'name': 'Enemigos a Amantes'}, 'fr': {'name': 'Ennemis à Amants'}}},
            {'name': 'Slow Burn', 'slug': 'slow-burn', 'category': 'relationship',
             'translations': {'zh': {'name': '慢热'}, 'es': {'name': 'Fuego Lento'}, 'fr': {'name': 'Feu Lent'}}},
            {'name': 'Love Triangle', 'slug': 'love-triangle', 'category': 'relationship',
             'translations': {'zh': {'name': '三角恋'}, 'es': {'name': 'Triángulo Amoroso'}, 'fr': {'name': 'Triangle Amoureux'}}},

            # Tone tags
            {'name': 'Comedy', 'slug': 'comedy', 'category': 'tone',
             'translations': {'zh': {'name': '喜剧'}, 'es': {'name': 'Comedia'}, 'fr': {'name': 'Comédie'}}},
        ]

        for data in tags_data:
            tag, created = Tag.objects.get_or_create(
                slug=data['slug'],
                defaults={
                    'name': data['name'],
                    'category': data['category'],
                    'translations': data.get('translations', {})
                }
            )
            if created:
                self.stdout.write(f'  Created tag: {tag.name} ({tag.category})')
            else:
                self.stdout.write(f'  Tag exists: {tag.name}')

    def seed_sample_books(self):
        """Create sample books with complete taxonomy"""
        # Get or create test user
        user, _ = User.objects.get_or_create(
            username='test_author',
            defaults={
                'email': 'test@example.com',
                'pen_name': 'Test Author'
            }
        )

        # Get languages
        try:
            lang_en = Language.objects.get(code='en')
            lang_zh = Language.objects.get(code='zh')
        except Language.DoesNotExist:
            self.stdout.write(self.style.WARNING('Languages not found, skipping sample books'))
            return

        # Get sections
        fiction = Section.objects.get(slug='fiction')
        bl = Section.objects.get(slug='bl')

        books_data = [
            {
                'canonical_title': 'The Immortal Cultivator',
                'section': fiction,
                'owner': user,
                'original_language': lang_zh,
                'genres': ['cultivation', 'xianxia'],
                'tags': ['strong-protagonist', 'system-user', 'fantasy-world', 'power-struggle'],
                'book_title': 'The Immortal Cultivator',
                'book_language': lang_en,
                'author': 'Test Author',
                'description': 'A young cultivator embarks on a journey to achieve immortality, aided by a mysterious system that grants him incredible powers.',
            },
            {
                'canonical_title': 'Reborn as a Villain',
                'section': fiction,
                'owner': user,
                'original_language': lang_zh,
                'genres': ['fantasy', 'urban-fantasy'],
                'tags': ['transmigration', 'smart-protagonist', 'modern-world', 'revenge'],
                'book_title': 'Reborn as a Villain',
                'book_language': lang_en,
                'author': 'Test Author',
                'description': 'After dying, the protagonist is reborn as the villain in a novel he once read. Can he change his fate?',
            },
            {
                'canonical_title': 'Heavenly Dao Master',
                'section': bl,
                'owner': user,
                'original_language': lang_zh,
                'genres': ['bl-cultivation'],
                'tags': ['strong-protagonist', 'ancient-china', 'slow-burn', 'enemies-to-lovers'],
                'book_title': 'Heavenly Dao Master',
                'book_language': lang_en,
                'author': 'Test Author',
                'description': 'Two rival cultivators from opposing sects find themselves drawn together by fate in their quest for enlightenment.',
            },
            {
                'canonical_title': 'Space Pirates Romance',
                'section': fiction,
                'owner': user,
                'original_language': lang_en,
                'genres': ['sci-fi', 'space-opera', 'romance'],
                'tags': ['strong-protagonist', 'enemies-to-lovers', 'mystery', 'comedy'],
                'book_title': 'Space Pirates Romance',
                'book_language': lang_en,
                'author': 'Test Author',
                'description': 'A bounty hunter and a charming space pirate must team up to solve a galaxy-spanning mystery.',
            },
        ]

        for book_data in books_data:
            # Create BookMaster
            bookmaster, bm_created = BookMaster.objects.get_or_create(
                canonical_title=book_data['canonical_title'],
                defaults={
                    'section': book_data['section'],
                    'owner': book_data['owner'],
                    'original_language': book_data['original_language'],
                }
            )

            if bm_created:
                self.stdout.write(f'  Created BookMaster: {bookmaster.canonical_title}')

                # Add genres
                for order, genre_slug in enumerate(book_data['genres'], 1):
                    try:
                        genre = Genre.objects.get(section=book_data['section'], slug=genre_slug)
                        BookGenre.objects.get_or_create(
                            bookmaster=bookmaster,
                            genre=genre,
                            defaults={'order': order}
                        )
                    except Genre.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f'    Genre not found: {genre_slug}'))

                # Add tags
                for tag_slug in book_data['tags']:
                    try:
                        tag = Tag.objects.get(slug=tag_slug)
                        BookTag.objects.get_or_create(
                            bookmaster=bookmaster,
                            tag=tag
                        )
                    except Tag.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f'    Tag not found: {tag_slug}'))

                # Create Book translation
                book, book_created = Book.objects.get_or_create(
                    bookmaster=bookmaster,
                    language=book_data['book_language'],
                    defaults={
                        'title': book_data['book_title'],
                        'author': book_data['author'],
                        'description': book_data['description'],
                        'is_public': True,
                        'progress': 'ongoing',
                    }
                )

                if book_created:
                    self.stdout.write(f'    Created Book: {book.title} ({book.language.code})')
            else:
                self.stdout.write(f'  BookMaster exists: {bookmaster.canonical_title}')

    def print_summary(self):
        """Print summary of created data"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('='*60)
        self.stdout.write(f'Sections: {Section.objects.count()}')
        self.stdout.write(f'Genres (Primary): {Genre.objects.filter(is_primary=True).count()}')
        self.stdout.write(f'Genres (Sub-genres): {Genre.objects.filter(is_primary=False).count()}')
        self.stdout.write(f'Tags: {Tag.objects.count()}')
        self.stdout.write(f'BookMasters: {BookMaster.objects.count()}')
        self.stdout.write(f'Books: {Book.objects.count()}')
        self.stdout.write('='*60)
