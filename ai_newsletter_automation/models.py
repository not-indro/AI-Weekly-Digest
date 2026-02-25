from dataclasses import dataclass
from datetime import date
from typing import List, Optional


@dataclass
class ArticleHit:
    title: str
    url: str
    snippet: str
    source: Optional[str] = None
    published: Optional[str] = None


@dataclass
class VerifiedArticle:
    title: str
    url: str
    snippet: str
    content: str
    published: Optional[str] = None
    scraped_published_date: Optional[str] = None


@dataclass
class SummaryItem:
    Headline: str
    Summary_Text: str
    Live_Link: str
    Date: Optional[str] = None  # ISO string if present (events)
    Relevance: Optional[int] = None  # 1-10 relevance rating from LLM
    Source: Optional[str] = None  # origin badge e.g. "arXiv", "TBS", "OECD"


@dataclass
class SectionConfig:
    name: str
    query: str
    limit: int
    require_date: bool = False
    description: Optional[str] = None
    fallback: Optional[List[str]] = None
    days: Optional[int] = None  # override default search window for this section
    # ── Per-section curation knobs ──
    include_domains: Optional[List[str]] = None   # prefer articles from these domains
    exclude_domains: Optional[List[str]] = None   # block these domains (section-level)
    relevance_threshold: int = 6                   # min LLM relevance score (1-10) to keep
    boost_keywords: Optional[List[str]] = None     # rank articles containing these higher
    reject_keywords: Optional[List[str]] = None    # drop articles matching these words
