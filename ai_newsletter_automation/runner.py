import concurrent.futures
import json
import os
import threading
from collections import OrderedDict
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Callable, Optional

import click
import requests

from .assemble import render_newsletter
from .config import get_settings
from .models import SummaryItem, VerifiedArticle, ArticleHit, SectionConfig
from .scrape import scrape, extract_metadata
from .search import (
    get_streams,
    search_stream,
    collect_trending,
    collect_events,
    collect_research,
    collect_ai_progress,
    collect_indian,
    collect_global,
    collect_deep_dive,
    _filter_by_keywords,
    _boost_by_keywords,
    _boost_by_source_quality,
    _sort_by_source_priority,
    _apply_time_decay,
)
from .dedup import deduplicate
from .rerank import rerank_articles
from .source_quality import SourceTracker
from .summarize import summarize_section, generate_tldr
from .verify import verify_link


SECTION_ORDER = [
    "trending",
    "indian",
    "global",
    "events",
    "ai_progress",
    "research_plain",
    "deep_dive",
]

_LOG_LOCK = threading.Lock()


def _log_skipped(reason: str, url: str, log: Path) -> None:
    """Best-effort logging — silently skip on read-only filesystems (Vercel)."""
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        # Thread-safe logging
        with _LOG_LOCK:
            with log.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"reason": reason, "url": url}) + "\n")
    except OSError:
        # Vercel serverless: filesystem is read-only, try /tmp
        try:
            tmp_log = Path("/tmp") / "logs" / log.name
            tmp_log.parent.mkdir(parents=True, exist_ok=True)
            with _LOG_LOCK:
                with tmp_log.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"reason": reason, "url": url}) + "\n")
        except OSError:
            pass  # Give up silently — logging is non-critical


def _process_single_hit(hit: ArticleHit, log_file: Path) -> Optional[VerifiedArticle]:
    if not hit.url:
        _log_skipped("missing_url", "", log_file)
        return None

    try:
        html = verify_link(hit.url)
    except Exception:
        html = None

    if html is None:
        # Link unreachable — but if we have a good RSS snippet, use it
        if hit.snippet and len(hit.snippet) > 80:
            _log_skipped("verify_failed_using_snippet", hit.url, log_file)
            return VerifiedArticle(
                title=hit.title,
                url=hit.url,
                snippet=hit.snippet,
                content=hit.snippet,
                published=hit.published,
            )
        else:
            _log_skipped("verify_failed", hit.url, log_file)
        return None

    try:
        content = scrape(hit.url, html=html)
    except Exception:
        content = None
        
    if not content:
        # Scrape failed — fall back to RSS snippet
        if hit.snippet and len(hit.snippet) > 40:
            _log_skipped("scrape_failed_using_snippet", hit.url, log_file)
            content = hit.snippet
        else:
            _log_skipped("scrape_failed", hit.url, log_file)
            return None
    
    # Extract metadata (date)
    try:
        meta = extract_metadata(html)
        scraped_date = meta.get("date")
    except Exception:
        scraped_date = None

    return VerifiedArticle(
        title=hit.title,
        url=hit.url,
        snippet=hit.snippet,
        content=content,
        published=hit.published,
        scraped_published_date=scraped_date,
    )


def process_hits(hits: List[ArticleHit], limit: int, log_file: Path) -> List[VerifiedArticle]:
    verified: List[VerifiedArticle] = []
    
    # Parallelize verification to avoid 60s timeout
    # Max 10 threads is a good balance for Vercel
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Submit candidate tasks (fetch a bit more than limit to ensure we fill it)
        candidates = hits[:limit * 3]
        future_to_hit = {
            executor.submit(_process_single_hit, hit, log_file): hit 
            for hit in candidates
        }
        
        for future in concurrent.futures.as_completed(future_to_hit):
            try:
                result = future.result()
                if result:
                    verified.append(result)
                    
                    # If we reached the limit, we can stop
                    if len(verified) >= limit:
                        break
            except Exception as e:
                # Log exception but don't crash
                _log_skipped(f"exception_{type(e).__name__}", "", log_file)
                
    return verified[:limit]


def process_section(key: str, days: int, max_per_stream: Optional[int] = None, lang: str = "en") -> List[SummaryItem]:
    """Generate summaries for a single newsletter section.

    This is the core function used by both the CLI and the Vercel API.
    Returns a list of SummaryItem dataclasses.
    """
    settings = get_settings()
    streams = get_streams(custom_limits=max_per_stream)

    if key not in streams:
        raise ValueError(f"Unknown section key: {key}")

    cfg = streams[key]

    collectors: Dict[str, Callable[[SectionConfig], List[ArticleHit]]] = {
        "trending": lambda c: collect_trending(c.days or days),
        "events": lambda c: collect_events(c.days or days),
        "research_plain": lambda c: collect_research(c.days or days),
        "ai_progress": lambda c: collect_ai_progress(c.days or days),
        "indian": lambda c: collect_indian(c.days or days),
        "global": lambda c: collect_global(c.days or days),
        "deep_dive": lambda c: collect_deep_dive(c.days or days),
    }

    log_file = settings.project_root / "logs" / f"run-{date.today().isoformat()}.jsonl"

    # Retry loop: Standard -> Expanded Window -> Relaxed Threshold
    # Attempt 0: Standard (days=7, thresh=default)
    # Vercel Optimization: Originally limited to 1 attempt to avoid 60s timeout.
    # We are restoring it to 3 to ensure sections populate when standard search yields 0 hits.
    max_attempts = 3
    
    for attempt in range(max_attempts):
        # Calculate dynamic settings for this attempt
        multiplier = 1 + attempt  # 1, 2, 3
        current_days = (cfg.days or days) * multiplier
        
        # Relax threshold on final attempt
        current_threshold = cfg.relevance_threshold
        if attempt == 2:
            current_threshold = max(4, cfg.relevance_threshold - 2)

        # Create temporary config for this run
        run_cfg = replace(cfg, days=current_days, relevance_threshold=current_threshold)

        # 1. Collection
        if key in collectors:
            hits = collectors[key](run_cfg)
        else:
            hits = search_stream(run_cfg, current_days)

        # Apply section-level curation pipeline:
        hits = _filter_by_keywords(hits, run_cfg.reject_keywords)
        hits = _boost_by_keywords(hits, run_cfg.boost_keywords)
        
        # 2b. Boost by historical source quality (SourceTracker)
        hits = _boost_by_source_quality(hits)

        # 2. Source priority (curated feeds first)
        hits = _sort_by_source_priority(hits)
        # 3. Time-decay (fresher articles rank higher within window)
        hits = _apply_time_decay(hits, current_days)

        _log_skipped(f"section_{key}_attempt_{attempt}_hits={len(hits)}", "", log_file)

        verified = process_hits(hits, run_cfg.limit * 2, log_file)
        verified = deduplicate(verified)
        verified = _filter_verified_articles_by_date(verified, current_days)

        # Rerank with potentially relaxed threshold
        verified = rerank_articles(verified, run_cfg)
        verified = verified[:run_cfg.limit]

        items = summarize_section(
            run_cfg.name, verified,
            require_date=run_cfg.require_date,
            section_key=key,
            lang=lang,
            relevance_threshold=run_cfg.relevance_threshold,
        )

        # Filter by date window (LLM hallucination check)
        items = _filter_items_by_date(items, current_days)
        
        final_items = [item for item in items if item.Live_Link]
        
        if final_items:
            # Success! Record success metric?
            if attempt > 0:
                print(f"  [OK] {key} populated on retry #{attempt} (days={current_days}, thresh={current_threshold})")
            
            # Record source quality
            tracker = SourceTracker()
            for item in final_items:
                if item.Live_Link and item.Relevance:
                    tracker.record(item.Live_Link, item.Relevance)
            
            return final_items
            
        # If we failed, loop continues to expand search
        
    return [] # Failed all attempts


def _filter_verified_articles_by_date(articles: List[VerifiedArticle], days: int) -> List[VerifiedArticle]:
    """Remove articles where the scraped date is definitely older than the search window."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    # Allow a small buffer (e.g. 24h) for timezone differences or late scraping
    cutoff -= timedelta(days=1)
    
    kept = []
    for a in articles:
        if not a.scraped_published_date:
            kept.append(a)
            continue
            
        # Try to parse the scraped date
        # It could be ISO, or other formats. We'll try a few common ones.
        try:
            # Most meta tags are ISO-like
            d_str = a.scraped_published_date[:19] # Truncate potential timezone for simple parsing
            # Try ISO format first
            pub = None
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
                try:
                    pub = datetime.strptime(d_str, fmt)
                    break
                except ValueError:
                    continue
            
            if pub and pub < cutoff:
                # Definitely old
                continue
        except Exception:
            # If parsing fails, be permissive and keep it
            pass
            
        kept.append(a)
        
    return kept


def _filter_items_by_date(items: List[SummaryItem], days: int) -> List[SummaryItem]:
    """Remove SummaryItems whose LLM-generated Date is older than the window."""
    cutoff = date.today() - timedelta(days=days)
    filtered = []
    for item in items:
        if not item.Date:
            # No date on item — keep it (date wasn't available)
            filtered.append(item)
            continue
        try:
            # Try parsing common LLM date formats
            d = item.Date.strip()
            parsed = None
            for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"):
                try:
                    parsed = datetime.strptime(d, fmt).date()
                    break
                except ValueError:
                    continue
            if parsed and parsed < cutoff:
                # Date is too old — skip this item
                continue
        except Exception:
            pass
        filtered.append(item)
    return filtered


@click.command()
@click.option("--since-days", default=None, type=int, help="How many days back to search.")
@click.option("--date", "run_date", default=None, help="Override date string YYYY-MM-DD.")
@click.option("--max-per-stream", default=None, type=int, help="Override max items per stream.")
@click.option("--dry-run", is_flag=True, default=False, help="Write HTML only, skip Outlook.")
@click.option("--lang", default="en", type=click.Choice(["en", "fr"]), help="Output language.")
@click.option("--workers", default=4, type=int, help="Number of parallel workers.")
def main(since_days, run_date, max_per_stream, dry_run, lang, workers):
    settings = get_settings()
    days = since_days or settings.run_days

    sections: Dict[str, List[SummaryItem]] = OrderedDict()
    
    click.echo(f"Starting generation with {workers} workers...")

    # Use ThreadPoolExecutor for parallel section processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        # Submit all tasks
        future_to_section = {
            executor.submit(process_section, key, days, max_per_stream, lang): key
            for key in SECTION_ORDER
        }
        
        # Collect results as they complete
        results = {}
        for future in concurrent.futures.as_completed(future_to_section):
            key = future_to_section[future]
            try:
                data = future.result()
                results[key] = data
                if len(data) == 0:
                    click.echo(f"  [SKIPPED] {key} returned 0 items")
                else:
                    click.echo(f"  [OK] {key} done ({len(data)} items)")
            except Exception as exc:
                click.echo(f"  [ERROR] {key} generated an exception: {exc}")
                results[key] = []

    # Reassemble in correct order
    for key in SECTION_ORDER:
        sections[key] = results.get(key, [])

    # Generate TL;DR from the top-relevance items across all sections
    click.echo("  -> generating TL;DR...")
    all_items = [item for items in sections.values() for item in items]
    all_items.sort(key=lambda x: x.Relevance or 0, reverse=True)
    tldr = generate_tldr(all_items[:6], lang=lang)

    html = render_newsletter(sections, run_date=run_date or date.today().isoformat(), tldr=tldr, lang=lang)

    suffix = f"-{lang}" if lang != "en" else ""
    output_path = settings.project_root / "output" / f"newsletter{suffix}.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    click.echo(f"Generated newsletter ({lang}) -> {output_path}")


if __name__ == "__main__":
    main()
