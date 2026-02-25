import re
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup

PAYWALL_PHRASES: Iterable[str] = (
    "subscribe to read",
    "log in to continue",
    "isaccessibleforfree\":false",
    "paywall",
    "subscriber-only",
    "subscription required",
    "already a subscriber",
)

SOFT_404_PHRASES: Iterable[str] = (
    "page not found",
    "404 not found",
    "this page doesn't exist",
    "this page does not exist",
    "no longer available",
    "has been removed",
    "content unavailable",
    "error 404",
    "we couldn't find",
    "we can't find",
)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AI-Newsletter/1.0; +https://example.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

MIN_CONTENT_LENGTH = 200  # chars — reject stub / error pages


def is_paywalled(html: str) -> bool:
    haystack = html.lower()
    return any(phrase in haystack for phrase in PAYWALL_PHRASES)


def is_soft_404(html: str) -> bool:
    """Detect pages that return HTTP 200 but are actually error / not-found pages."""
    haystack = html[:20_000].lower()
    return any(phrase in haystack for phrase in SOFT_404_PHRASES)


def verify_link(url: str, timeout: int = 4) -> Optional[str]:
    """Fetch *url* and return the HTML if the page is reachable, is HTML,
    has enough content, and is not behind a paywall or soft-404.
    Returns ``None`` on any failure so that the caller can skip the article."""
    try:
        resp = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    # Too many redirects is suspicious (login walls, etc.)
    if len(resp.history) > 5:
        return None

    content_type = resp.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return None

    text = resp.text
    sample = text[:100_000]

    # Minimum content check — reject stubs and error pages
    soup = BeautifulSoup(sample, "html.parser")
    body_text = soup.get_text(separator=" ", strip=True)
    if len(body_text) < MIN_CONTENT_LENGTH:
        return None

    # Soft-404 detection
    if is_soft_404(sample):
        return None

    # Paywall detection
    if is_paywalled(sample):
        return None

    # Additional JSON-LD paywall flag
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            if "isAccessibleForFree" in script.text and '"isaccessibleforfree": false' in script.text.lower():
                return None
        except Exception:
            continue

    return text
