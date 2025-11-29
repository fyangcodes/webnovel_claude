"""
Locust load testing configuration for Web Novel application.

Run with:
    locust -f locustfile.py --host=http://localhost:8000
"""

from locust import HttpUser, task, between
import random


class WebNovelUser(HttpUser):
    """
    Simulates a typical web novel reader browsing the site.

    Weight distribution:
    - 40% homepage/section browsing
    - 30% book detail viewing
    - 20% book list browsing
    - 10% search
    """

    wait_time = between(1, 5)

    def on_start(self):
        self.languages = ['en', 'zh-hans']
        self.sections = ['fiction', 'bl', 'gl']
        self.book_slugs = [
            'space-pirates-romance',
            'heavenly-dao-master',
            'reborn-as-a-villain',
        ]
        self.sort_options = ['oldest', 'latest', 'new']

    @task(20)
    def view_homepage(self):
        """View homepage (section home)."""
        language = random.choice(self.languages)
        section = random.choice(self.sections)

        with self.client.get(
            f"/{language}/{section}/",
            catch_response=True,
            name="Homepage"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")

    @task(15)
    def view_book_detail(self):
        """View book detail page."""
        language = random.choice(self.languages)
        section = random.choice(self.sections)
        book = random.choice(self.book_slugs)

        with self.client.get(
            f"/{language}/{section}/book/{book}/",
            catch_response=True,
            name="Book Detail"
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")

    @task(10)
    def view_book_list(self):
        """View book list page."""
        language = random.choice(self.languages)
        section = random.choice(self.sections)

        with self.client.get(
            f"/{language}/{section}/books/",
            catch_response=True,
            name="Book List"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")

    @task(5)
    def search_books(self):
        """Search for books."""
        language = random.choice(self.languages)
        section = random.choice(self.sections)
        query = random.choice(['space', 'romance', 'fantasy'])

        with self.client.get(
            f"/{language}/{section}/search/?q={query}",
            catch_response=True,
            name="Search"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")
