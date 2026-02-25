import json
import sys
import os
from http.server import BaseHTTPRequestHandler
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_newsletter_automation.assemble import render_newsletter
from ai_newsletter_automation.models import SummaryItem


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

        sections = {}
        for key, items_raw in data.get("sections", {}).items():
            sections[key] = [
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

        run_date = data.get("run_date", date.today().isoformat())
        tldr = data.get("tldr", [])
        lang = data.get("lang", "en")
        html = render_newsletter(sections, run_date=run_date, tldr=tldr, lang=lang)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
