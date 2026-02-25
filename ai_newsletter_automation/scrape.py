import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .verify import DEFAULT_HEADERS


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # Collapse whitespace
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


def fetch_article(url: str, timeout: int = 10) -> Optional[str]:
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return None
        if "text/html" not in resp.headers.get("Content-Type", ""):
            return None
        return resp.text
    except requests.RequestException:
        return None


def scrape(url: str, html: Optional[str] = None) -> Optional[str]:
    if html is None:
        html = fetch_article(url)
    if not html:
        return None
    text = extract_text(html)
    # Keep it reasonably bounded for LLM cost
    return text[:20_000]


def extract_metadata(html: str) -> dict:
    """Extract metadata (published date, etc.) from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    meta = {}

    # 1. Try standard meta tags
    # <meta property="article:published_time" content="...">
    # <meta name="pubdate" content="...">
    # <meta name="date" content="...">
    for selector in [
        {"property": "article:published_time"},
        {"name": "pubdate"},
        {"name": "date"},
        {"name": "DC.date.issued"},
        {"name": "sailthru.date"},
    ]:
        tag = soup.find("meta", attrs=selector)
        if tag and tag.get("content"):
            meta["date"] = tag["content"]
            break

    # 2. Try JSON-LD if no meta tag found
    if not meta.get("date"):
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = script.string
                if not data:
                    continue
                # simplistic approach: regex (safer than json.load on arbitrary web junk)
                # look for "datePublished": "..."
                match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', data)
                if match:
                    meta["date"] = match.group(1)
                    break
            except Exception:
                continue

    # 3. Try <time> tag
    if not meta.get("date"):
        time_tag = soup.find("time")
        if time_tag:
            if time_tag.get("datetime"):
                meta["date"] = time_tag["datetime"]
            elif time_tag.get("content"):
                meta["date"] = time_tag["content"]

    return meta
