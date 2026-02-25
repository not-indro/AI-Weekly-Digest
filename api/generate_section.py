import json
import sys
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add project root to path so the package can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_newsletter_automation.runner import process_section, SECTION_ORDER
from ai_newsletter_automation.models import SummaryItem
from ai_newsletter_automation.search import get_streams


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        key = params.get("key", [None])[0]
        days = int(params.get("days", ["7"])[0])
        lang = params.get("lang", ["en"])[0]
        # Optional per-request curation overrides
        limit_override = params.get("limit", [None])[0]
        relevance_override = params.get("relevance_threshold", [None])[0]

        if not key:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Missing 'key' parameter",
                "valid_keys": SECTION_ORDER,
            }).encode())
            return

        if key not in SECTION_ORDER:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": f"Unknown section key: {key}",
                "valid_keys": SECTION_ORDER,
            }).encode())
            return

        # Check for critical configuration
        groq_key = os.getenv("GROQ_API_KEY")
        tavily_key = os.getenv("TAVILY_API_KEY")
        if not groq_key or not tavily_key:
            missing = []
            if not groq_key: missing.append("GROQ_API_KEY")
            if not tavily_key: missing.append("TAVILY_API_KEY")
            
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": f"Missing configuration on server: {', '.join(missing)}",
                "valid_keys": SECTION_ORDER,
            }).encode())
            return

        try:
            # Apply per-request overrides if provided
            max_per_stream = int(limit_override) if limit_override else None
            items = process_section(key, days, max_per_stream=max_per_stream, lang=lang)
            result = {
                "section_key": key,
                "items": [
                    {
                        "Headline": item.Headline,
                        "Summary_Text": item.Summary_Text,
                        "Live_Link": item.Live_Link,
                        "Date": item.Date,
                        "Relevance": item.Relevance,
                        "Source": item.Source,
                    }
                    for item in items
                ],
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        except Exception as exc:
            # Return partial success (empty items) instead of hard-failing.
            # This prevents rate-limit cascades from marking every section red.
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "section_key": key,
                "items": [],
                "error": str(exc),
                "warning": str(exc),
            }).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
