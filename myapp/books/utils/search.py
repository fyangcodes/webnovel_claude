"""
Book Search Service

Provides keyword-based search functionality using the BookKeyword denormalized index.
Supports multi-language search with weighted relevance ranking.
"""

import time
from typing import Dict, List, Any, Optional
from django.db.models import Q, Count, Sum, F, Case, When, FloatField
from books.models import BookKeyword, Book, BookMaster


class BookSearchService:
    """
    Stateless service for searching books by keywords.

    Uses the BookKeyword denormalized index for fast multi-language search
    with weighted relevance ranking.
    """

    # Match type weights for scoring
    EXACT_MATCH_WEIGHT = 3.0
    PREFIX_MATCH_WEIGHT = 2.0
    CONTAINS_MATCH_WEIGHT = 1.0

    @staticmethod
    def normalize_query(query: str) -> List[str]:
        """
        Normalize and tokenize search query.

        Args:
            query: Raw search query string

        Returns:
            List of normalized tokens
        """
        # Convert to lowercase and strip
        query = query.lower().strip()

        # Split on whitespace and filter empty strings
        tokens = [token for token in query.split() if token]

        return tokens

    @staticmethod
    def search(
        query: str,
        language_code: str,
        section_slug: Optional[str] = None,
        genre_slug: Optional[str] = None,
        tag_slug: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Search for books by keyword with optional filters.

        Args:
            query: Search query string
            language_code: Language to search in
            section_slug: Optional section filter
            genre_slug: Optional genre filter
            tag_slug: Optional tag filter
            status: Optional status filter (ongoing/completed)
            limit: Maximum number of results to return

        Returns:
            Dictionary containing:
                - books: List of Book objects
                - total_results: Total count of results
                - matched_keywords: List of matched keywords
                - search_time_ms: Search duration in milliseconds
        """
        start_time = time.time()

        # Normalize query
        tokens = BookSearchService.normalize_query(query)

        if not tokens:
            return {
                'books': [],
                'total_results': 0,
                'matched_keywords': [],
                'search_time_ms': 0
            }

        # Build keyword matching query
        keyword_query = Q()
        for token in tokens:
            # Match keywords that contain the token (case-insensitive)
            keyword_query |= Q(keyword__icontains=token)

        # Find matching keywords for the language
        matching_keywords = BookKeyword.objects.filter(
            keyword_query,
            language_code=language_code
        ).select_related('bookmaster')

        if not matching_keywords.exists():
            return {
                'books': [],
                'total_results': 0,
                'matched_keywords': [],
                'search_time_ms': int((time.time() - start_time) * 1000)
            }

        # Calculate relevance scores for each bookmaster
        bookmaster_scores = {}
        matched_keyword_list = []

        for kw in matching_keywords:
            bookmaster_id = kw.bookmaster_id
            keyword_lower = kw.keyword.lower()

            # Track matched keywords (unique)
            if keyword_lower not in matched_keyword_list:
                matched_keyword_list.append(keyword_lower)

            # Calculate match type weight
            match_weight = 0.0
            for token in tokens:
                token_lower = token.lower()
                if keyword_lower == token_lower:
                    # Exact match
                    match_weight = max(match_weight, BookSearchService.EXACT_MATCH_WEIGHT)
                elif keyword_lower.startswith(token_lower):
                    # Prefix match
                    match_weight = max(match_weight, BookSearchService.PREFIX_MATCH_WEIGHT)
                elif token_lower in keyword_lower:
                    # Contains match
                    match_weight = max(match_weight, BookSearchService.CONTAINS_MATCH_WEIGHT)

            # Calculate total score: keyword_weight * match_weight
            score = kw.weight * match_weight

            # Accumulate scores for each bookmaster
            if bookmaster_id in bookmaster_scores:
                bookmaster_scores[bookmaster_id] += score
            else:
                bookmaster_scores[bookmaster_id] = score

        # Get bookmasters sorted by score
        sorted_bookmasters = sorted(
            bookmaster_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Get bookmaster IDs in order
        bookmaster_ids = [bm_id for bm_id, score in sorted_bookmasters[:limit]]

        # Get books for these bookmasters with filters
        books_query = Book.objects.filter(
            bookmaster_id__in=bookmaster_ids,
            language__code=language_code,
            is_public=True
        ).select_related(
            'bookmaster',
            'bookmaster__section',
            'language'
        ).prefetch_related(
            'bookmaster__book_genres__genre',
            'bookmaster__book_genres__genre__parent',
            'bookmaster__book_tags__tag'
        )

        # Apply filters
        if section_slug:
            books_query = books_query.filter(bookmaster__section__slug=section_slug)

        if genre_slug:
            books_query = books_query.filter(bookmaster__book_genres__genre__slug=genre_slug)

        if tag_slug:
            books_query = books_query.filter(bookmaster__book_tags__tag__slug=tag_slug)

        if status:
            books_query = books_query.filter(progress=status)

        # Execute query
        books = list(books_query)

        # Sort books by bookmaster score
        bookmaster_score_map = dict(sorted_bookmasters)
        books.sort(key=lambda b: bookmaster_score_map.get(b.bookmaster_id, 0), reverse=True)

        # Limit results
        books = books[:limit]

        end_time = time.time()
        search_time_ms = int((end_time - start_time) * 1000)

        return {
            'books': books,
            'total_results': len(books),
            'matched_keywords': matched_keyword_list,
            'search_time_ms': search_time_ms
        }

    @staticmethod
    def autocomplete(
        query: str,
        language_code: str,
        limit: int = 10
    ) -> List[str]:
        """
        Get autocomplete suggestions for a search query.

        Args:
            query: Partial search query
            language_code: Language to search in
            limit: Maximum number of suggestions

        Returns:
            List of keyword suggestions
        """
        if not query or len(query) < 2:
            return []

        # Normalize query
        query_lower = query.lower().strip()

        # Find keywords that start with the query
        keywords = BookKeyword.objects.filter(
            keyword__istartswith=query_lower,
            language_code=language_code
        ).values('keyword').annotate(
            count=Count('id')
        ).order_by('-count', 'keyword')[:limit]

        return [kw['keyword'] for kw in keywords]
