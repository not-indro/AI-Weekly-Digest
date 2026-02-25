import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_newsletter_automation.models import SummaryItem
from ai_newsletter_automation.summarize import generate_tldr


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON body"}).encode())
            return

        items_raw = data.get("items", [])
        items = [
            SummaryItem(
                Headline=it.get("Headline", ""),
                Summary_Text=it.get("Summary_Text", ""),
                Live_Link=it.get("Live_Link", ""),
                Date=it.get("Date"),
                Relevance=it.get("Relevance"),
                Source=it.get("Source"),
            )
            for it in items_raw
        ]

        lang = data.get("lang", "en")
        tldr = generate_tldr(items, lang=lang)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"tldr": tldr}).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
