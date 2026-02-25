"""Tests for advanced curation features: dedup, time-decay, UTM tracking, source quality."""

import time
from datetime import datetime, timedelta

from ai_newsletter_automation.models import ArticleHit, VerifiedArticle, SummaryItem
from ai_newsletter_automation.dedup import deduplicate, _title_similarity
from ai_newsletter_automation.search import _apply_time_decay
from ai_newsletter_automation.assemble import _add_utm
from ai_newsletter_automation.source_quality import SourceTracker, _extract_domain


# ── Dedup tests ──

def _make_verified(title="Test", url="https://example.com", content=""):
    return VerifiedArticle(title=title, url=url, snippet="", content=content)


def test_title_similarity_identical():
    assert _title_similarity("Hello World", "Hello World") == 1.0


def test_title_similarity_different():
    assert _title_similarity("AI revolution", "cooking recipes") < 0.4


def test_title_similarity_partial():
    score = _title_similarity(
        "OpenAI launches GPT-5 model",
        "OpenAI launches new GPT-5 AI model"
    )
    assert score >= 0.7


def test_deduplicate_removes_near_duplicates():
    articles = [
        _make_verified("OpenAI launches GPT-5", "https://a.com/1", content="Full article text here with details"),
        _make_verified("OpenAI launches GPT-5 model today", "https://b.com/2", content="Short"),
        _make_verified("Totally different article about farming", "https://c.com/3", content="Farming content"),
    ]
    result = deduplicate(articles)
    assert len(result) == 2
    # Should keep the one with more content
    assert result[0].url == "https://a.com/1"
    assert result[1].url == "https://c.com/3"


def test_deduplicate_keeps_unique():
    articles = [
        _make_verified("Google unveils quantum computing breakthrough", "https://a.com/1"),
        _make_verified("New recipe book wins culinary award", "https://b.com/2"),
        _make_verified("FIFA World Cup 2030 venues announced", "https://c.com/3"),
    ]
    result = deduplicate(articles)
    assert len(result) == 3


def test_deduplicate_empty():
    assert deduplicate([]) == []


def test_deduplicate_single():
    articles = [_make_verified("Only one")]
    assert deduplicate(articles) == articles


# ── Time-decay tests ──

def _make_hit(title="Test", published=None, url="https://example.com"):
    return ArticleHit(title=title, url=url, snippet="", published=published)


def test_time_decay_orders_by_freshness():
    now = datetime.utcnow()
    hits = [
        _make_hit("Old", published=(now - timedelta(days=6)).strftime("%Y-%m-%d")),
        _make_hit("New", published=(now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")),
        _make_hit("Mid", published=(now - timedelta(days=3)).strftime("%Y-%m-%d")),
    ]
    result = _apply_time_decay(hits, days=7)
    assert result[0].title == "New"
    assert result[1].title == "Mid"
    assert result[2].title == "Old"


def test_time_decay_undated_articles_middle():
    now = datetime.utcnow()
    hits = [
        _make_hit("Fresh", published=now.strftime("%Y-%m-%d")),
        _make_hit("Undated", published=None),
        _make_hit("Old", published=(now - timedelta(days=6)).strftime("%Y-%m-%d")),
    ]
    result = _apply_time_decay(hits, days=7)
    # Fresh (score ~1.0) > Undated (0.5) > Old (score ~0.14)
    assert result[0].title == "Fresh"
    assert result[1].title == "Undated"
    assert result[2].title == "Old"


def test_time_decay_empty():
    assert _apply_time_decay([], 7) == []


# ── UTM tracking tests ──

def test_add_utm_basic():
    result = _add_utm("https://example.com/article", "trending", "2026-02-19")
    assert "utm_source=ai_this_week" in result
    assert "utm_medium=email" in result
    assert "utm_campaign=2026-02-19" in result
    assert "utm_content=trending" in result


def test_add_utm_preserves_existing_params():
    result = _add_utm("https://example.com/article?foo=bar", "canadian", "2026-02-19")
    assert "foo=bar" in result
    assert "utm_source=ai_this_week" in result


def test_add_utm_no_overwrite_existing_utm():
    result = _add_utm("https://example.com?utm_source=other", "trending", "2026-02-19")
    assert "utm_source=other" in result
    # Should NOT have utm_source=ai_this_week since it already exists
    assert "utm_source=ai_this_week" not in result


def test_add_utm_empty():
    assert _add_utm("", "trending", "2026-02-19") == ""


# ── Source quality tests ──

def test_extract_domain():
    assert _extract_domain("https://www.example.com/path") == "example.com"
    assert _extract_domain("https://sub.example.com/path") == "sub.example.com"
    assert _extract_domain("") == ""


def test_source_tracker_get_boost_unknown():
    """Unknown domains should return 0.0 boost."""
    tracker = SourceTracker()
    assert tracker.get_boost("https://never-seen-before-domain-xyz.com/") == 0.0
