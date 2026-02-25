from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Iterable

import requests
import feedparser
from urllib.parse import urlparse, urlunparse, parse_qs, unquote
from duckduckgo_search import DDGS

from .config import get_settings
from .models import ArticleHit, SectionConfig
from .source_quality import SourceTracker


# ── Domain blocklist — evergreen / non-news pages that pollute results ──

BLOCKED_DOMAINS = {
    "en.wikipedia.org",
    "wikipedia.org",
    "investopedia.com",
    "techopedia.com",
    "builtin.com",
    "coursera.org",
    "udemy.com",
    "medium.com",       # often paywalled or generic
    "quora.com",
}

BLOCKED_URL_PATTERNS = (
    "/wiki/",
    "/about",
    "/contact",
    "/careers",
    "/privacy",
    "/terms",
)


DEFAULT_STREAMS: Dict[str, SectionConfig] = {
    "trending": SectionConfig(
        name="Trending AI",
        query='"artificial intelligence" OR "AI" major announcement OR launch OR release this week',
        limit=8,
        relevance_threshold=7,
        boost_keywords=["GPT", "Claude", "Gemini", "open source", "regulation"],
    ),
    "indian": SectionConfig(
        name="Indian News",
        query='"Artificial Intelligence" AND (India OR "Indian government" OR "startup" OR "tech")',
        limit=5,
        include_domains=["indiatimes.com", "thehindu.com", "timesofindia.indiatimes.com", "indianexpress.com", "business-standard.com"],
        relevance_threshold=6,
        boost_keywords=["MeitY", "IndiaAI", "government", "startup", "NITI Aayog", "investment"],
    ),
    "global": SectionConfig(
        name="Global News",
        query='"AI" AND (regulation OR governance OR "executive order" OR policy) AND (EU OR US OR UK OR G7 OR OECD OR UN) -Canada',
        limit=5,
        relevance_threshold=6,
        boost_keywords=["EU AI Act", "executive order", "OECD", "G7", "regulation"],
        reject_keywords=["crypto", "blockchain", "NFT"],
    ),
    "events": SectionConfig(
        name="Events",
        query='AI conference OR AI summit OR "artificial intelligence" event OR "machine learning" workshop 2026',
        limit=4,
        require_date=True,
        relevance_threshold=5,
    ),

    "ai_progress": SectionConfig(
        name="AI Progress",
        query='AI language model benchmark state of the art 2026',
        limit=3,
        days=14,
        relevance_threshold=6,
        boost_keywords=["benchmark", "SOTA", "leaderboard", "accuracy"],
    ),
    "research_plain": SectionConfig(
        name="AI Research",
        query='AI artificial intelligence new research breakthrough paper 2026',
        limit=3,
        days=14,
        relevance_threshold=5,
        boost_keywords=["breakthrough", "novel", "state-of-the-art"],
    ),
    "deep_dive": SectionConfig(
        name="Deep Dive",
        query='AI policy regulation report whitepaper 2026',
        limit=2,
        days=14,
        relevance_threshold=7,
        boost_keywords=["report", "whitepaper", "framework", "policy"],
    ),
}


# ── Helpers ──


def _since_timestamp(days: int) -> str:
    cutoff = datetime.utcnow() - timedelta(days=days)
    return cutoff.strftime("%Y-%m-%d")


def _is_blocked_url(url: str) -> bool:
    """Return True if the URL belongs to a blocked domain or matches a blocked pattern."""
    try:
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        if any(domain.endswith(b) for b in BLOCKED_DOMAINS):
            return True
        path = parsed.path.lower()
        if any(p in path for p in BLOCKED_URL_PATTERNS):
            return True
    except Exception:
        pass
    return False


def _normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        cleaned = parsed._replace(query="", fragment="")
        return urlunparse(cleaned)
    except Exception:
        return url


def _dedupe(hits: List[ArticleHit]) -> List[ArticleHit]:
    seen = set()
    unique = []
    for h in hits:
        key = (_normalize_url(h.url).lower(), h.title.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(h)
    return unique


def _parse_date_str(date_str: Optional[str]) -> Optional[datetime]:
    """Best-effort parse of a date string into a datetime object."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(date_str.strip()[:25], fmt)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except (ValueError, AttributeError):
            continue
    return None


# Sources whose articles are trusted enough to keep even without a date.
_TRUSTED_SOURCES = {"Google Alert", "arXiv", "PapersWithCode", "RSS", "DuckDuckGo"}


def _filter_by_date(hits: List[ArticleHit], days: int) -> List[ArticleHit]:
    """Remove hits whose published date is outside the search window.
    Articles with no parseable date are rejected UNLESS they come from a
    trusted source (curated RSS, Google Alerts, arXiv, etc.)."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    filtered = []
    for h in hits:
        pub = _parse_date_str(h.published)
        if pub is None:
            # No date — allow through only if from a trusted source
            if h.source and h.source in _TRUSTED_SOURCES:
                filtered.append(h)
            continue
        if pub < cutoff:
            # Too old — skip
            continue
        filtered.append(h)
    return filtered


def _filter_blocked(hits: List[ArticleHit], extra_excludes: Optional[Iterable[str]] = None) -> List[ArticleHit]:
    """Remove hits from blocked domains or URL patterns.
    Optionally applies section-level exclude_domains on top of the global blocklist."""
    filtered = [h for h in hits if not _is_blocked_url(h.url)]
    if extra_excludes:
        exclude_set = {d.lower() for d in extra_excludes}
        filtered = [
            h for h in filtered
            if not any((urlparse(h.url).hostname or "").endswith(d) for d in exclude_set)
        ]
    return filtered


def _filter_by_keywords(hits: List[ArticleHit], reject_keywords: Optional[List[str]]) -> List[ArticleHit]:
    """Remove hits whose title or snippet contains any reject keyword (case-insensitive)."""
    if not reject_keywords:
        return hits
    reject_lower = [k.lower() for k in reject_keywords]
    filtered = []
    for h in hits:
        text = f"{h.title} {h.snippet}".lower()
        if any(k in text for k in reject_lower):
            continue
        filtered.append(h)
    return filtered


def _boost_by_keywords(hits: List[ArticleHit], boost_keywords: Optional[List[str]]) -> List[ArticleHit]:
    """Stable-sort hits so articles containing boost keywords appear first."""
    if not boost_keywords:
        return hits
    boost_lower = [k.lower() for k in boost_keywords]

    def score(h: ArticleHit) -> int:
        text = f"{h.title} {h.snippet}".lower()
        return sum(1 for k in boost_lower if k in text)

    return sorted(hits, key=score, reverse=True)


def _boost_by_source_quality(hits: List[ArticleHit]) -> List[ArticleHit]:
    """Sort articles so that domains with high historical relevance appear first.
    
    Uses SourceTracker to get a quality boost (0.0-1.0) for each domain.
    """
    tracker = SourceTracker()
    
    # Cache boosts to avoid repeated disk reads if SourceTracker wasn't cached
    # (SourceTracker implementation reads JSON on every record/get_boost call in current form,
    # but for a batch sort we can just call it. Optimization: SourceTracker could cache data)
    
    def score(h: ArticleHit) -> float:
        return tracker.get_boost(h.url)
        
    # Stable sort: high boost first
    return sorted(hits, key=score, reverse=True)


# Source priority for sorting — lower number = higher priority.
_SOURCE_PRIORITY = {
    "Google Alert": 0,
    "RSS": 1,
    "arXiv": 1,
    "PapersWithCode": 1,
}
_DEFAULT_SOURCE_PRIORITY = 5  # Tavily and unknown sources


def _sort_by_source_priority(hits: List[ArticleHit]) -> List[ArticleHit]:
    """Stable-sort hits so curated sources (Google Alerts, RSS) rank above web search."""
    return sorted(
        hits,
        key=lambda h: _SOURCE_PRIORITY.get(h.source or "", _DEFAULT_SOURCE_PRIORITY),
    )


def _apply_time_decay(hits: List[ArticleHit], days: int) -> List[ArticleHit]:
    """Stable-sort hits so fresher articles rank higher within the search window.

    Computes a freshness score (0.0 = oldest in window, 1.0 = published today).
    Articles without a parseable date get a neutral 0.5 score.
    """
    if not hits or days <= 0:
        return hits

    now = datetime.utcnow()

    def freshness(h: ArticleHit) -> float:
        pub = _parse_date_str(h.published)
        if pub is None:
            return 0.5  # neutral — don't penalize or reward undated articles
        
        # Ensure naive UTC for comparison
        if pub.tzinfo is not None:
            pub = pub.astimezone(timezone.utc).replace(tzinfo=None)
            
        age_days = (now - pub).total_seconds() / 86400
        return max(0.0, 1.0 - (age_days / days))

    return sorted(hits, key=freshness, reverse=True)


# ── Tavily search ──


def search_stream(section: SectionConfig, days: int) -> List[ArticleHit]:
    settings = get_settings()
    max_results = settings.max_per_stream or section.limit * 3

    payload = {
        "query": section.query,
        "api_key": settings.tavily_api_key,
        "max_results": max_results,
        "search_depth": "advanced",
        "include_domains": section.include_domains,
        "days": days,
    }

    hits: List[ArticleHit] = []

    try:
        resp = requests.post("https://api.tavily.com/search", json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        
        for res in data.get("results", []):
            hits.append(
                ArticleHit(
                    title=res.get("title", "").strip(),
                    url=res.get("url", ""),
                    snippet=res.get("content", "").strip(),
                    source=res.get("source"),
                    published=res.get("published_date"),
                )
            )
            
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 432:
            print(f"  [FALLBACK] Tavily API limit reached (432). Using DuckDuckGo for: {section.name}")
            try:
                # Fallback to duckduckgo-search news endpoint
                ddgs_results = DDGS().news(
                    keywords=section.query,
                    max_results=max_results,
                )
                for res in ddgs_results:
                    hits.append(
                        ArticleHit(
                            title=res.get("title", "").strip(),
                            url=res.get("url", ""),
                            snippet=res.get("body", "").strip(),
                            source="DuckDuckGo",
                            published=res.get("date"),
                        )
                    )
            except Exception as ddg_e:
                print(f"  [ERROR] DuckDuckGo fallback failed for {section.name}: {ddg_e}")
        else:
            print(f"  [ERROR] Tavily API error for {section.name}: {e}")
    except Exception as e:
        print(f"  [ERROR] Request failed for {section.name}: {e}")

    # Post-filter: date + blocked domains (global + section-level excludes)
    hits = _filter_blocked(hits, extra_excludes=section.exclude_domains)
    hits = _filter_by_date(hits, days)
    # Apply section-level keyword filtering and boosting
    hits = _filter_by_keywords(hits, section.reject_keywords)
    hits = _boost_by_keywords(hits, section.boost_keywords)
    return hits


# ── Trending Collectors ──


HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
AI_KEYWORDS = ("ai", "artificial", "llm", "model", "gpt", "transformer", "openai", "anthropic", "gemini")


def fetch_hn_trending(limit: int = 30, days: int = 7) -> List[ArticleHit]:
    cutoff_ts = (datetime.utcnow() - timedelta(days=days)).timestamp()
    try:
        top_ids = requests.get(f"{HN_API_BASE}/topstories.json", timeout=10).json()[: limit * 2]
        best_ids = requests.get(f"{HN_API_BASE}/beststories.json", timeout=10).json()[: limit]
        ids = list(dict.fromkeys(top_ids + best_ids))
    except Exception:
        return []

    hits: List[ArticleHit] = []
    for story_id in ids:
        try:
            item = requests.get(f"{HN_API_BASE}/item/{story_id}.json", timeout=5).json()
            title = item.get("title", "")
            if not title or not any(k in title.lower() for k in AI_KEYWORDS):
                continue
            # Date filter: reject items older than the search window
            item_time = item.get("time", 0)
            if item_time < cutoff_ts:
                continue
            url = item.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
            if _is_blocked_url(url):
                continue
            pub_dt = datetime.utcfromtimestamp(item_time)
            hits.append(ArticleHit(
                title=title, url=url, snippet="Hacker News trending",
                published=pub_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            ))
            if len(hits) >= limit:
                break
        except Exception:
            continue
    return hits


def fetch_producthunt_trending(limit: int = 10, days: int = 7) -> List[ArticleHit]:
    rss_url = "https://www.producthunt.com/feeds/topic/artificial-intelligence"
    cutoff = datetime.utcnow() - timedelta(days=days)
    try:
        feed = feedparser.parse(rss_url)
    except Exception:
        return []
    hits: List[ArticleHit] = []
    for entry in feed.entries[:limit * 2]:
        # Date filter
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if published:
            pub_dt = datetime(*published[:6])
            if pub_dt < cutoff:
                continue
        elif not published:
            # No date available — skip to avoid stale content
            continue
        url = entry.get("link", "")
        if _is_blocked_url(url):
            continue
        hits.append(
            ArticleHit(
                title=entry.get("title", ""),
                url=url,
                snippet="Product Hunt AI launch",
                published=entry.get("published"),
            )
        )
        if len(hits) >= limit:
            break
    return hits


CURATED_FEEDS = [
    "https://blog.openai.com/rss/",
    "https://www.anthropic.com/feed",                       # Anthropic
    "https://blog.google/technology/ai/rss/",               # Google AI
    "https://deepmind.google/blog/rss/",                    # Google DeepMind
    "https://blogs.microsoft.com/ai/feed/",                 # Microsoft AI
    "https://www.microsoft.com/en-us/research/feed/",       # Microsoft Research
    "https://www.technologyreview.com/feed/",               # MIT Tech Review
    "https://ai.meta.com/blog/rss/",                        # Meta AI
    "https://blog.research.google/feeds/posts/default",     # Google Research
    "https://www.oecd.ai/feed",
    "https://hai.stanford.edu/rss.xml",
    "https://www.oneusefulthing.org/feed",                # Ethan Mollick (Substack)
]


# ── Google Alert RSS feeds (from Feedly subscriptions) ──

GOOGLE_ALERT_FEEDS: Dict[str, List[str]] = {
    "trending": [
        "https://www.google.com/alerts/feeds/03030665084568507357/6619274340374812968",       # AGI
        "https://www.google.com/alerts/feeds/03030665084568507357/5237285988387868375",       # ASI
        "https://www.google.com/alerts/feeds/03030665084568507357/11653796448320099668",      # Job Replacement - AI
    ],
    "indian": [
        # Google Alert feeds for India removed to prioritize Tavily search
    ],
    "global": [
        "https://www.google.com/alerts/feeds/03030665084568507357/2891758781116511337",       # Ethics - AI
        "https://www.google.com/alerts/feeds/03030665084568507357/2278791836030122678",       # Governance - AI
        "https://www.google.com/alerts/feeds/03030665084568507357/16866512384761599386",      # Privacy - AI
        "https://www.google.com/alerts/feeds/03030665084568507357/7622957089141856354",       # Regulation - AI
        "https://www.google.com/alerts/feeds/03030665084568507357/15942459126004772098",      # Security - AI
    ],
}


def fetch_curated_feeds(limit: int = 10, days: int = 7) -> List[ArticleHit]:
    hits: List[ArticleHit] = []
    cutoff = datetime.utcnow() - timedelta(days=days)
    for url in CURATED_FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue
        for entry in feed.entries:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                pub_dt = datetime(*published[:6])
                if pub_dt < cutoff:
                    continue
            else:
                # No date — skip to avoid stale content
                continue
            link = entry.get("link", "")
            if _is_blocked_url(link):
                continue
            hits.append(
                ArticleHit(
                    title=entry.get("title", ""),
                    url=link,
                    snippet=entry.get("summary", "")[:500],
                    published=entry.get("published"),
                )
            )
            if len(hits) >= limit:
                break
        if len(hits) >= limit:
            break
    return hits


def _unwrap_google_redirect(url: str) -> str:
    """Extract the real article URL from a Google Alerts redirect wrapper.
    Google Alerts links look like: https://www.google.com/url?...&url=REAL_URL&...
    Returns the original URL unchanged if it's not a redirect."""
    try:
        parsed = urlparse(url)
        if parsed.hostname and "google.com" in parsed.hostname and parsed.path == "/url":
            params = parse_qs(parsed.query)
            real = params.get("url") or params.get("q")
            if real:
                return unquote(real[0])
    except Exception:
        pass
    return url


def fetch_google_alerts(section_key: str, limit: int = 15, days: int = 7) -> List[ArticleHit]:
    """Fetch articles from Google Alert RSS feeds mapped to a newsletter section."""
    urls = GOOGLE_ALERT_FEEDS.get(section_key, [])
    if not urls:
        return []
    hits: List[ArticleHit] = []
    cutoff = datetime.utcnow() - timedelta(days=days)
    for url in urls:
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue
        for entry in feed.entries:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                pub_dt = datetime(*published[:6])
                if pub_dt < cutoff:
                    continue
            else:
                continue
            # Unwrap Google redirect to get the real article URL
            link = _unwrap_google_redirect(entry.get("link", ""))
            if _is_blocked_url(link):
                continue
            hits.append(
                ArticleHit(
                    title=entry.get("title", ""),
                    url=link,
                    snippet=entry.get("summary", "")[:500],
                    published=entry.get("published"),
                    source="Google Alert",
                )
            )
            if len(hits) >= limit:
                return _dedupe(hits)
    return _dedupe(hits)


def collect_trending(days: int) -> List[ArticleHit]:
    hits: List[ArticleHit] = []
    hits.extend(fetch_google_alerts("trending", limit=10, days=days))
    hits.extend(fetch_hn_trending(limit=20, days=days))
    hits.extend(fetch_producthunt_trending(limit=10, days=days))
    hits.extend(fetch_curated_feeds(limit=15, days=days))
    # Tavily fallback
    trending_cfg = SectionConfig(name="Trending AI", query='"AI" AND ("top news" OR trending) AND week', limit=8)
    hits.extend(search_stream(trending_cfg, days))
    return _dedupe(hits)




# ── Research Plain ──


def collect_research(days: int) -> List[ArticleHit]:
    # arXiv recent AI/ML
    max_results = 25
    query = "cat:cs.AI+OR+cat:cs.LG+OR+cat:stat.ML"
    url = f"http://export.arxiv.org/api/query?search_query={query}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"
    cutoff = datetime.utcnow() - timedelta(days=days)
    hits: List[ArticleHit] = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            published = entry.get("published_parsed")
            if published:
                pub_dt = datetime(*published[:6])
                if pub_dt < cutoff:
                    continue
            else:
                # No date — skip
                continue
            hits.append(
                ArticleHit(
                    title=entry.get("title", "").replace("\n", " ").strip(),
                    url=entry.get("link", ""),
                    snippet=entry.get("summary", "").replace("\n", " ")[:600],
                    published=entry.get("published"),
                    source="arXiv",
                )
            )
            if len(hits) >= 12:
                break
    except Exception:
        pass
    return _dedupe(hits)


# ── AI Progress ──


def _fetch_pwc_trending(limit: int = 10, days: int = 30) -> List[ArticleHit]:
    rss_url = "https://paperswithcode.com/trending?format=rss"
    cutoff = datetime.utcnow() - timedelta(days=days)
    try:
        feed = feedparser.parse(rss_url)
    except Exception:
        return []
    hits: List[ArticleHit] = []
    for entry in feed.entries[:limit * 2]:
        # Date filter
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if published:
            pub_dt = datetime(*published[:6])
            if pub_dt < cutoff:
                continue
        else:
            # No date — skip to avoid stale content
            continue
        url = entry.get("link", "")
        if _is_blocked_url(url):
            continue
        hits.append(
            ArticleHit(
                title=entry.get("title", ""),
                url=url,
                snippet=entry.get("summary", "")[:400],
                source="PapersWithCode",
                published=entry.get("published"),
            )
        )
        if len(hits) >= limit:
            break
    return hits


def collect_ai_progress(days: int) -> List[ArticleHit]:
    hits: List[ArticleHit] = []
    hits.extend(_fetch_pwc_trending(limit=15, days=days))
    # Tavily fallback — PapersWithCode RSS is often empty for short windows
    hits.extend(search_stream(DEFAULT_STREAMS["ai_progress"], days))
    return _dedupe(hits)


# ── Indian News (Google Alerts + Tavily) ──


def collect_indian(days: int) -> List[ArticleHit]:
    """Prioritise Google Alert RSS for Indian AI news, Tavily as fallback."""
    hits: List[ArticleHit] = []
    hits.extend(fetch_google_alerts("indian", limit=10, days=days))
    hits.extend(search_stream(DEFAULT_STREAMS["indian"], days))
    return _dedupe(hits)



# ── Global News (Google Alerts + Tavily) ──


def collect_global(days: int) -> List[ArticleHit]:
    """Prioritise Google Alert RSS for global AI policy news, Tavily as fallback."""
    hits: List[ArticleHit] = []
    hits.extend(fetch_google_alerts("global", limit=10, days=days))
    hits.extend(search_stream(DEFAULT_STREAMS["global"], days))
    return _dedupe(hits)


# ── Events (general AI conferences / webinars) ──


EVENT_FEEDS = [
    "https://www.aiconference.com/feed/",
    "https://developer.nvidia.com/blog/feed/",
    "https://events.linuxfoundation.org/feed/",
]

EVENT_QUERIES = [
    SectionConfig(name="Events", query='AI conference OR AI summit OR "artificial intelligence" event 2026', limit=4, require_date=True),
    SectionConfig(name="Events", query='AI webinar OR AI workshop OR "machine learning" event upcoming', limit=4, require_date=True),
]


def _fetch_event_feeds(days: int) -> List[ArticleHit]:
    """Fetch AI event announcements from RSS feeds."""
    hits: List[ArticleHit] = []
    cutoff = datetime.utcnow() - timedelta(days=days)
    for url in EVENT_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                title = entry.get("title", "").lower()
                # only keep entries that look event-related
                if not any(k in title for k in ("conference", "summit", "event", "webinar", "workshop", "meetup", "hackathon", "ai", "ml")):
                    continue
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    pub_dt = datetime(*published[:6])
                    if pub_dt < cutoff:
                        continue
                else:
                    continue
                link = entry.get("link", "")
                if _is_blocked_url(link):
                    continue
                hits.append(
                    ArticleHit(
                        title=entry.get("title", ""),
                        url=link,
                        snippet=entry.get("summary", "")[:400],
                        source="RSS",
                        published=entry.get("published"),
                    )
                )
        except Exception:
            continue
    return hits


def collect_events(days: int) -> List[ArticleHit]:
    """Search for upcoming AI events — multiple sources for resilience."""
    hits: List[ArticleHit] = []

    # RSS feeds first
    try:
        hits.extend(_fetch_event_feeds(days))
    except Exception:
        pass

    # Multiple Tavily queries as fallback
    for query_cfg in EVENT_QUERIES:
        try:
            hits.extend(search_stream(query_cfg, days))
        except Exception:
            continue

    # Original default query as final fallback
    if not hits:
        try:
            hits.extend(search_stream(DEFAULT_STREAMS["events"], days))
        except Exception:
            pass

    return _dedupe(hits)


# ── Deep Dive (long-form reports from major orgs) ──


REPORT_FEEDS = [
    "https://www.nist.gov/artificial-intelligence/rss.xml",
]


def collect_deep_dive(days: int) -> List[ArticleHit]:
    """Search for in-depth AI reports from OECD, Anthropic, MIT, METR, NIST, etc."""
    hits: List[ArticleHit] = []
    # Tavily search
    hits.extend(search_stream(DEFAULT_STREAMS["deep_dive"], days))
    # RSS feeds from report-publishing orgs
    cutoff = datetime.utcnow() - timedelta(days=days)
    for url in REPORT_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    pub_dt = datetime(*published[:6])
                    if pub_dt < cutoff:
                        continue
                else:
                    continue
                link = entry.get("link", "")
                if _is_blocked_url(link):
                    continue
                hits.append(
                    ArticleHit(
                        title=entry.get("title", ""),
                        url=link,
                        snippet=entry.get("summary", "")[:500],
                        source="RSS",
                        published=entry.get("published"),
                    )
                )
        except Exception:
            continue
    return _dedupe(hits)



def get_streams(custom_limits: int | None = None) -> Dict[str, SectionConfig]:
    streams: Dict[str, SectionConfig] = {}
    for key, cfg in DEFAULT_STREAMS.items():
        new_cfg = replace(cfg)
        if custom_limits:
            new_cfg.limit = custom_limits
        streams[key] = new_cfg
    return streams
