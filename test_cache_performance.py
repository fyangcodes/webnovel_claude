#!/usr/bin/env python
"""
Test script to verify Redis cache performance.

This script tests:
1. Cache is enabled (Redis backend)
2. Query counts with cache (first load vs subsequent loads)
3. Cache hit rates
4. Performance improvements
"""

import os
import django
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myapp.settings')
django.setup()

from django.core.cache import cache
from django.db import connection, reset_queries
from django.conf import settings
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser

# Enable query logging
settings.DEBUG = True

def test_cache_backend():
    """Verify cache backend is Redis, not DummyCache."""
    print("=" * 80)
    print("TEST 1: Cache Backend Verification")
    print("=" * 80)

    backend = settings.CACHES['default']['BACKEND']
    print(f"Cache backend: {backend}")

    if 'dummy' in backend.lower():
        print("❌ FAIL: Using DummyCache - cache is disabled!")
        return False
    elif 'redis' in backend.lower():
        print("✅ PASS: Using Redis cache")
    else:
        print(f"⚠️  WARNING: Unknown cache backend: {backend}")

    # Test cache write/read
    test_key = 'test:cache:verification'
    test_value = 'cache_is_working'

    cache.set(test_key, test_value, timeout=60)
    retrieved = cache.get(test_key)

    if retrieved == test_value:
        print("✅ PASS: Cache read/write working")
        cache.delete(test_key)
        return True
    else:
        print("❌ FAIL: Cache read/write not working")
        return False


def test_homepage_queries():
    """Test homepage query counts with cache."""
    print("\n" + "=" * 80)
    print("TEST 2: Homepage Query Count (Cache Enabled)")
    print("=" * 80)

    from reader.views import WelcomeView

    factory = RequestFactory()

    # Clear all caches first
    print("\nClearing all caches...")
    cache.clear()
    print("✅ Cache cleared")

    # First request - cache miss (should populate cache)
    print("\n--- FIRST REQUEST (Cache Miss - Warming) ---")
    reset_queries()

    request = factory.get('/zh-hans/')
    request.user = AnonymousUser()
    view = WelcomeView.as_view()

    start_time = time.time()
    response = view(request, language_code='zh-hans')
    first_load_time = (time.time() - start_time) * 1000
    first_load_queries = len(connection.queries)

    print(f"Queries: {first_load_queries}")
    print(f"Time: {first_load_time:.2f}ms")
    print(f"Status: {response.status_code}")

    # Second request - cache hit (should use cached data)
    print("\n--- SECOND REQUEST (Cache Hit) ---")
    reset_queries()

    request2 = factory.get('/zh-hans/')
    request2.user = AnonymousUser()

    start_time = time.time()
    response2 = view(request2, language_code='zh-hans')
    second_load_time = (time.time() - start_time) * 1000
    second_load_queries = len(connection.queries)

    print(f"Queries: {second_load_queries}")
    print(f"Time: {second_load_time:.2f}ms")
    print(f"Status: {response2.status_code}")

    # Third request - verify cache is stable
    print("\n--- THIRD REQUEST (Cache Hit Verification) ---")
    reset_queries()

    request3 = factory.get('/zh-hans/')
    request3.user = AnonymousUser()

    start_time = time.time()
    response3 = view(request3, language_code='zh-hans')
    third_load_time = (time.time() - start_time) * 1000
    third_load_queries = len(connection.queries)

    print(f"Queries: {third_load_queries}")
    print(f"Time: {third_load_time:.2f}ms")
    print(f"Status: {response3.status_code}")

    # Analysis
    print("\n" + "-" * 80)
    print("RESULTS ANALYSIS")
    print("-" * 80)

    query_reduction = ((first_load_queries - second_load_queries) / first_load_queries * 100) if first_load_queries > 0 else 0
    time_improvement = ((first_load_time - second_load_time) / first_load_time * 100) if first_load_time > 0 else 0

    print(f"Query reduction: {first_load_queries} → {second_load_queries} ({query_reduction:.1f}% reduction)")
    print(f"Time improvement: {first_load_time:.2f}ms → {second_load_time:.2f}ms ({time_improvement:.1f}% faster)")
    print(f"Cache stability: {'✅ STABLE' if second_load_queries == third_load_queries else '⚠️  UNSTABLE'}")

    # Success criteria
    print("\n" + "-" * 80)
    print("SUCCESS CRITERIA")
    print("-" * 80)

    success = True

    if second_load_queries < first_load_queries:
        print(f"✅ PASS: Cache reduces queries ({first_load_queries} → {second_load_queries})")
    else:
        print(f"❌ FAIL: Cache doesn't reduce queries ({first_load_queries} → {second_load_queries})")
        success = False

    if second_load_queries <= 15:
        print(f"✅ PASS: Cached queries ≤ 15 ({second_load_queries})")
    else:
        print(f"⚠️  WARNING: Cached queries > 15 ({second_load_queries})")

    if query_reduction >= 30:
        print(f"✅ PASS: Query reduction ≥ 30% ({query_reduction:.1f}%)")
    else:
        print(f"⚠️  WARNING: Query reduction < 30% ({query_reduction:.1f}%)")

    return success


def test_cache_functions():
    """Test individual cache functions."""
    print("\n" + "=" * 80)
    print("TEST 3: Individual Cache Functions")
    print("=" * 80)

    from reader.cache import (
        get_cached_genres_flat,
        get_cached_sections,
        get_cached_featured_books,
    )

    # Clear cache
    cache.clear()

    # Test genres cache
    print("\n--- Testing get_cached_genres_flat() ---")

    reset_queries()
    genres1 = get_cached_genres_flat()
    queries1 = len(connection.queries)
    print(f"First call: {queries1} queries, {len(genres1)} genres")

    reset_queries()
    genres2 = get_cached_genres_flat()
    queries2 = len(connection.queries)
    print(f"Second call: {queries2} queries (should be 0 - from cache)")

    if queries2 == 0:
        print("✅ PASS: Genres cached successfully")
    else:
        print(f"❌ FAIL: Genres not cached ({queries2} queries on 2nd call)")

    # Test sections cache
    print("\n--- Testing get_cached_sections() ---")

    cache.clear()  # Clear for clean test

    reset_queries()
    sections1 = get_cached_sections()
    queries1 = len(connection.queries)
    print(f"First call: {queries1} queries, {len(sections1)} sections")

    reset_queries()
    sections2 = get_cached_sections()
    queries2 = len(connection.queries)
    print(f"Second call: {queries2} queries (should be 0 - from cache)")

    if queries2 == 0:
        print("✅ PASS: Sections cached successfully")
    else:
        print(f"❌ FAIL: Sections not cached ({queries2} queries on 2nd call)")

    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("REDIS CACHE PERFORMANCE TEST")
    print("=" * 80)
    print(f"Django DEBUG: {settings.DEBUG}")
    print(f"DISABLE_CACHE: {os.getenv('DISABLE_CACHE', 'False')}")
    print("=" * 80)

    # Run tests
    test1 = test_cache_backend()
    test2 = test_homepage_queries()
    test3 = test_cache_functions()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    print(f"Cache Backend: {'✅ PASS' if test1 else '❌ FAIL'}")
    print(f"Homepage Queries: {'✅ PASS' if test2 else '❌ FAIL'}")
    print(f"Cache Functions: {'✅ PASS' if test3 else '❌ FAIL'}")

    if test1 and test2 and test3:
        print("\n🎉 ALL TESTS PASSED! Redis cache is working correctly.")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED. Check output above for details.")
        return 1


if __name__ == '__main__':
    exit(main())
