from ai_newsletter_automation.models import ArticleHit
from ai_newsletter_automation.search import (
    _filter_by_date,
    _is_blocked_url,
    _unwrap_google_redirect,
    _filter_by_keywords,
    _boost_by_keywords,
    _sort_by_source_priority,
    _filter_blocked,
    DEFAULT_STREAMS,
    _TRUSTED_SOURCES,
)


def test_filter_by_date_rejects_dateless_untrusted():
    """Undated articles from unknown sources should be rejected."""
    hits = [
        ArticleHit(title="No Date", url="https://example.com/1", snippet="s"),
        ArticleHit(title="Has Date", url="https://example.com/2", snippet="s", published="2026-02-18"),
    ]
    filtered = _filter_by_date(hits, days=30)
    assert len(filtered) == 1
    assert filtered[0].title == "Has Date"


def test_filter_by_date_allows_trusted_undated():
    """Undated articles from trusted sources (Google Alert, arXiv, etc.) should pass."""
    hits = [
        ArticleHit(title="Google Alert", url="https://example.com/1", snippet="s", source="Google Alert"),
        ArticleHit(title="arXiv Paper", url="https://arxiv.org/abs/123", snippet="s", source="arXiv"),
        ArticleHit(title="Random Blog", url="https://example.com/2", snippet="s", source="SomeRandomSite"),
        ArticleHit(title="No Source", url="https://example.com/3", snippet="s"),
    ]
    filtered = _filter_by_date(hits, days=7)
    assert len(filtered) == 2
    titles = {h.title for h in filtered}
    assert "Google Alert" in titles
    assert "arXiv Paper" in titles
    assert "Random Blog" not in titles
    assert "No Source" not in titles


def test_filter_by_date_rejects_old():
    """Articles older than the window should be filtered out."""
    hits = [
        ArticleHit(title="Old", url="https://example.com/1", snippet="s", published="2020-01-01"),
        ArticleHit(title="Recent", url="https://example.com/2", snippet="s", published="2026-02-18"),
    ]
    filtered = _filter_by_date(hits, days=7)
    assert len(filtered) == 1
    assert filtered[0].title == "Recent"


def test_unwrap_google_redirect():
    """Google Alert redirect URLs should be unwrapped to the real article URL."""
    wrapped = "https://www.google.com/url?rct=j&sa=t&url=https%3A%2F%2Fwww.reuters.com%2Fai-article&ct=ga"
    result = _unwrap_google_redirect(wrapped)
    assert result == "https://www.reuters.com/ai-article"


def test_unwrap_google_redirect_passthrough():
    """Non-redirect URLs should pass through unchanged."""
    normal = "https://www.reuters.com/ai-article"
    assert _unwrap_google_redirect(normal) == normal


def test_is_blocked_url_wikipedia():
    assert _is_blocked_url("https://en.wikipedia.org/wiki/Artificial_intelligence") is True


def test_is_blocked_url_allowed():
    assert _is_blocked_url("https://www.reuters.com/article/123") is False


def test_default_queries_no_single_words():
    """All Tavily queries should be multi-word and targeted, not generic single-word."""
    for key, cfg in DEFAULT_STREAMS.items():
        words = cfg.query.strip().split()
        assert len(words) > 2, f"Section '{key}' query too short/generic: '{cfg.query}'"


def test_trusted_sources_set():
    """Trusted source set should contain expected RSS/feed source types."""
    assert "Google Alert" in _TRUSTED_SOURCES
    assert "arXiv" in _TRUSTED_SOURCES
    assert "PapersWithCode" in _TRUSTED_SOURCES
    assert "RSS" in _TRUSTED_SOURCES


# ── New curation feature tests ──


def test_filter_by_keywords_rejects():
    """Articles matching reject keywords are removed."""
    hits = [
        ArticleHit(title="AI in Agriculture", url="https://a.com/1", snippet="Crop prediction with ML"),
        ArticleHit(title="Crypto AI Trading Bot", url="https://a.com/2", snippet="Blockchain meets AI"),
        ArticleHit(title="Wheat Quality AI", url="https://a.com/3", snippet="Grain grading models"),
    ]
    filtered = _filter_by_keywords(hits, reject_keywords=["crypto", "blockchain"])
    assert len(filtered) == 2
    titles = {h.title for h in filtered}
    assert "Crypto AI Trading Bot" not in titles


def test_filter_by_keywords_no_reject():
    """When no reject keywords are given, all articles pass through."""
    hits = [
        ArticleHit(title="AI News", url="https://a.com/1", snippet="stuff"),
    ]
    assert _filter_by_keywords(hits, reject_keywords=None) == hits
    assert _filter_by_keywords(hits, reject_keywords=[]) == hits


def test_boost_by_keywords_ordering():
    """Articles containing boost keywords should sort to the front."""
    hits = [
        ArticleHit(title="Generic AI news", url="https://a.com/1", snippet="nothing special"),
        ArticleHit(title="TBS Policy Update", url="https://a.com/2", snippet="Federal Treasury Board"),
        ArticleHit(title="ISED Announcement", url="https://a.com/3", snippet="Innovation Canada"),
    ]
    boosted = _boost_by_keywords(hits, boost_keywords=["TBS", "Treasury Board", "federal"])
    # TBS article should be first (matches 3 keywords: TBS, Treasury Board, Federal)
    assert boosted[0].title == "TBS Policy Update"


def test_sort_by_source_priority():
    """Google Alert and RSS sources should rank above Tavily/unknown sources."""
    hits = [
        ArticleHit(title="Tavily Result", url="https://a.com/1", snippet="s", source=None),
        ArticleHit(title="Google Alert", url="https://a.com/2", snippet="s", source="Google Alert"),
        ArticleHit(title="RSS Feed", url="https://a.com/3", snippet="s", source="RSS"),
        ArticleHit(title="Another Web", url="https://a.com/4", snippet="s", source="Reuters"),
    ]
    sorted_hits = _sort_by_source_priority(hits)
    assert sorted_hits[0].source == "Google Alert"
    assert sorted_hits[1].source == "RSS"


def test_filter_blocked_with_section_excludes():
    """Section-level exclude_domains should block articles from those domains."""
    hits = [
        ArticleHit(title="Reddit post", url="https://reddit.com/r/ai/123", snippet="s"),
        ArticleHit(title="Good article", url="https://reuters.com/article", snippet="s"),
    ]
    filtered = _filter_blocked(hits, extra_excludes=["reddit.com"])
    assert len(filtered) == 1
    assert filtered[0].title == "Good article"


def test_section_configs_have_valid_thresholds():
    """All section relevance_threshold values must be between 1 and 10."""
    for key, cfg in DEFAULT_STREAMS.items():
        assert 1 <= cfg.relevance_threshold <= 10, (
            f"Section '{key}' has invalid relevance_threshold: {cfg.relevance_threshold}"
        )


def test_section_configs_days_override():
    """Sections with days set should have reasonable values."""
    for key, cfg in DEFAULT_STREAMS.items():
        if cfg.days is not None:
            assert cfg.days > 0, f"Section '{key}' has non-positive days: {cfg.days}"
            assert cfg.days <= 30, f"Section '{key}' has excessively large days: {cfg.days}"
    # Verify specific overrides exist
    assert DEFAULT_STREAMS["deep_dive"].days == 14
    assert DEFAULT_STREAMS["ai_progress"].days == 14
    assert DEFAULT_STREAMS["research_plain"].days == 14
