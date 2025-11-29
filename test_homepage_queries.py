#!/usr/bin/env python
"""Test script to count actual queries on homepage view"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, '/home/user/code/webnovel_claude/myapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myapp.settings')
django.setup()

from django.test import RequestFactory
from django.db import connection, reset_queries
from django.conf import settings

# Enable query logging
settings.DEBUG = True

from reader.views import HomePageView

def test_homepage_queries():
    """Test actual query count on homepage"""
    factory = RequestFactory()
    request = factory.get('/zh-hans/')

    # Reset query counter
    reset_queries()

    # Create view and call get_context_data
    view = HomePageView()
    view.setup(request)
    view.object_list = []

    try:
        context = view.get_context_data()

        query_count = len(connection.queries)
        print(f"\n{'='*60}")
        print(f"HOMEPAGE QUERY COUNT: {query_count}")
        print(f"{'='*60}\n")

        # Group queries by type
        query_types = {}
        for q in connection.queries:
            sql = q['sql']
            # Identify query type
            if 'books_book' in sql and 'SELECT' in sql:
                key = 'Book SELECT'
            elif 'books_genre' in sql:
                key = 'Genre queries'
            elif 'books_tag' in sql:
                key = 'Tag queries'
            elif 'reader_styleconfig' in sql:
                key = 'StyleConfig queries'
            elif 'books_chapter' in sql:
                key = 'Chapter queries'
            else:
                key = 'Other'

            query_types[key] = query_types.get(key, 0) + 1

        print("Query breakdown:")
        for qtype, count in sorted(query_types.items()):
            print(f"  {qtype}: {count}")

        # Show first 10 queries in detail
        print(f"\n{'='*60}")
        print("First 10 queries (detailed):")
        print(f"{'='*60}\n")
        for i, q in enumerate(connection.queries[:10], 1):
            print(f"{i}. {q['sql'][:200]}...")
            print(f"   Time: {q['time']}s\n")

        # Check for duplicate queries
        query_signatures = {}
        for q in connection.queries:
            # Normalize query (remove specific IDs)
            sig = q['sql'].split('WHERE')[0] if 'WHERE' in q['sql'] else q['sql']
            query_signatures[sig] = query_signatures.get(sig, 0) + 1

        duplicates = {k: v for k, v in query_signatures.items() if v > 1}
        if duplicates:
            print(f"\n{'='*60}")
            print(f"DUPLICATE QUERY PATTERNS FOUND: {len(duplicates)}")
            print(f"{'='*60}\n")
            for sig, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"Executed {count} times:")
                print(f"  {sig[:150]}...\n")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_homepage_queries()
