#!/usr/bin/env python
"""Test cache performance on homepage."""
import time
from django.core.cache import cache
from django.db import connection, reset_queries
from django.conf import settings
from django.test import Client

settings.DEBUG = True

print("=" * 70)
print("HOMEPAGE QUERY COUNT WITH REDIS CACHE")
print("=" * 70)

# Create client
client = Client()

# Clear cache
print("\n1. Clearing Redis cache...")
cache.clear()
print("   ✅ Cache cleared")

# First request
print("\n2. First request (cache warming)...")
reset_queries()
start = time.time()
response1 = client.get('/zh-hans/')
time1 = (time.time() - start) * 1000
queries1 = len(connection.queries)
print(f"   Queries: {queries1}")
print(f"   Time: {time1:.2f}ms")
print(f"   Status: {response1.status_code}")

# Second request
print("\n3. Second request (cache hit)...")
reset_queries()
start = time.time()
response2 = client.get('/zh-hans/')
time2 = (time.time() - start) * 1000
queries2 = len(connection.queries)
print(f"   Queries: {queries2}")
print(f"   Time: {time2:.2f}ms")
print(f"   Status: {response2.status_code}")

# Third request
print("\n4. Third request (verify stability)...")
reset_queries()
start = time.time()
response3 = client.get('/zh-hans/')
time3 = (time.time() - start) * 1000
queries3 = len(connection.queries)
print(f"   Queries: {queries3}")
print(f"   Time: {time3:.2f}ms")
print(f"   Status: {response3.status_code}")

# Analysis
print("\n" + "=" * 70)
print("RESULTS")
print("=" * 70)

reduction = ((queries1 - queries2) / queries1 * 100) if queries1 > 0 else 0
from_baseline = ((26 - queries2) / 26 * 100)

print(f"\nCache warming: {queries1} queries")
print(f"Cache hit:     {queries2} queries")
print(f"Stable:        {queries3} queries")
print(f"\nReduction: {queries1} -> {queries2} ({reduction:.1f}%)")
print(f"From baseline (26 queries with cache disabled): {from_baseline:.1f}% reduction")

print("\n" + "=" * 70)
print("EVALUATION")
print("=" * 70)

if queries2 <= 12:
    print(f"\n✅ EXCELLENT: {queries2} queries (target: ≤12)")
elif queries2 <= 15:
    print(f"\n✅ GOOD: {queries2} queries (target: ≤15)")
else:
    print(f"\n⚠️  Above target: {queries2} queries")

if from_baseline >= 50:
    print(f"✅ EXCELLENT: {from_baseline:.1f}% reduction from baseline!")
elif from_baseline >= 30:
    print(f"✅ GOOD: {from_baseline:.1f}% reduction from baseline")

if queries2 == queries3:
    print(f"✅ Cache is stable")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"\nBefore optimization (no cache): 74 queries")
print(f"With query optimizations only:  26 queries (64.9% reduction)")
print(f"With Redis cache enabled:        {queries2} queries ({((74-queries2)/74*100):.1f}% total reduction)")
print()
