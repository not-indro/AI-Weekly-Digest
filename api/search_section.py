"""Step 1 of 2: Search for articles for a newsletter section.

SERVERLESS-OPTIMIZED: Skips full HTML scraping to stay under 60s.
Uses Tavily search snippets directly, which are rich enough for LLM
summarization. Full scraping is only available via the CLI.
"""
import json
import sys
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_newsletter_automation.search import (
    get_streams,
    collect_trending, collect_events,
    collect_research, collect_ai_progress, collect_indian,
    collect_global, collect_deep_dive,
    search_stream,
    _filter_by_keywords,
    _boost_by_keywords,
    _boost_by_source_quality,
    _sort_by_source_priority,
    _apply_time_decay,
)
from ai_newsletter_automation.runner import SECTION_ORDER


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        key = params.get("key", [None])[0]
        days = int(params.get("days", ["7"])[0])
        limit_override = params.get("limit", [None])[0]

        if not key or key not in SECTION_ORDER:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": f"Invalid or missing 'key': {key}",
            }).encode())
            return

        # Check Tavily key
        if not os.getenv("TAVILY_API_KEY"):
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Missing TAVILY_API_KEY on server",
            }).encode())
            return

        try:
            streams = get_streams(custom_limits=int(limit_override) if limit_override else None)
            cfg = streams[key]

            collectors = {
                "trending": lambda c: collect_trending(c.days or days),
                "events": lambda c: collect_events(c.days or days),
                "research_plain": lambda c: collect_research(c.days or days),
                "ai_progress": lambda c: collect_ai_progress(c.days or days),
                "indian": lambda c: collect_indian(c.days or days),
                "global": lambda c: collect_global(c.days or days),
                "deep_dive": lambda c: collect_deep_dive(c.days or days),
            }

            # Collection (Tavily search — fast, returns snippets)
            if key in collectors:
                hits = collectors[key](cfg)
            else:
                hits = search_stream(cfg, cfg.days or days)

            # Lightweight curation (no scraping, no verification)
            hits = _filter_by_keywords(hits, cfg.reject_keywords)
            hits = _boost_by_keywords(hits, cfg.boost_keywords)
            hits = _boost_by_source_quality(hits)
            hits = _sort_by_source_priority(hits)
            hits = _apply_time_decay(hits, cfg.days or days)

            # Simple dedup by URL
            seen_urls = set()
            unique_hits = []
            for h in hits:
                if h.url and h.url not in seen_urls:
                    seen_urls.add(h.url)
                    unique_hits.append(h)
            hits = unique_hits[:cfg.limit]

            result = {
                "section_key": key,
                "articles": [
                    {
                        "title": h.title or "",
                        "url": h.url or "",
                        "snippet": h.snippet or "",
                        "content": h.snippet or "",  # Use snippet as content
                        "published": h.published or "",
                    }
                    for h in hits
                ],
                "count": len(hits),
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        except Exception as exc:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "section_key": key,
                "articles": [],
                "count": 0,
                "error": str(exc),
            }).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
