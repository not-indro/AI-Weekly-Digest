"""Semantic deduplication — removes near-duplicate articles covering the same story."""

import logging
from difflib import SequenceMatcher
from typing import List

from .models import VerifiedArticle

log = logging.getLogger(__name__)

# Articles with title similarity above this threshold are considered duplicates
_SIMILARITY_THRESHOLD = 0.6


def _title_similarity(a: str, b: str) -> float:
    """Case-insensitive SequenceMatcher ratio between two titles."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _best_article(group: List[VerifiedArticle]) -> VerifiedArticle:
    """From a group of duplicates, keep the one with the richest content."""
    return max(group, key=lambda a: len(a.content or ""))


def deduplicate(
    articles: List[VerifiedArticle],
    threshold: float = _SIMILARITY_THRESHOLD,
) -> List[VerifiedArticle]:
    """Remove near-duplicate articles, keeping the highest-quality version.

    Uses title similarity via SequenceMatcher (no API calls needed).
    Preserves original ordering of the kept articles.
    """
    if len(articles) <= 1:
        return articles

    # Build clusters of similar articles
    clusters: List[List[int]] = []  # each cluster is a list of indices
    assigned: set = set()

    for i in range(len(articles)):
        if i in assigned:
            continue
        cluster = [i]
        assigned.add(i)
        for j in range(i + 1, len(articles)):
            if j in assigned:
                continue
            if _title_similarity(articles[i].title, articles[j].title) >= threshold:
                cluster.append(j)
                assigned.add(j)
        clusters.append(cluster)

    # Pick the best article from each cluster, preserving order
    result: List[VerifiedArticle] = []
    for cluster in clusters:
        group = [articles[idx] for idx in cluster]
        best = _best_article(group)
        result.append(best)
        if len(cluster) > 1:
            dupes = [articles[idx].title for idx in cluster if articles[idx] != best]
            log.info("Dedup: kept '%s', removed %d duplicates: %s", best.title, len(dupes), dupes)

    log.info("Deduplicated %d → %d articles", len(articles), len(result))
    return result
