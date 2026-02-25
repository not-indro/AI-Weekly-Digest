"""Source quality tracking — records domain-level relevance and feedback for auto-boosting."""

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

log = logging.getLogger(__name__)

# Rolling window for quality data (seconds)
_WINDOW_SECONDS = 90 * 24 * 3600  # 90 days
_FEEDBACK_PENALTY_SECONDS = 7 * 24 * 3600  # 7-day penalty for flagged domains


def _get_quality_path() -> Path:
    """Quality data file — tries project logs first, falls back to /tmp."""
    try:
        from .config import get_settings
        p = get_settings().project_root / "logs" / "source_quality.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        p = Path("/tmp") / "logs" / "source_quality.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


def _get_feedback_path() -> Path:
    """Feedback data file — tries project logs first, falls back to /tmp."""
    try:
        from .config import get_settings
        p = get_settings().project_root / "logs" / "feedback.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        p = Path("/tmp") / "logs" / "feedback.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


def _extract_domain(url: str) -> str:
    """Extract root domain from URL."""
    hostname = urlparse(url).hostname or ""
    # Strip www prefix
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname.lower()


def _load_json(path: Path) -> List[dict]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save_json(path: Path, data: List[dict]) -> None:
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        log.warning("Could not write source quality data to %s", path)


class SourceTracker:
    """Tracks domain-level quality scores from past newsletter runs."""

    def __init__(self):
        self._quality_path = _get_quality_path()
        self._feedback_path = _get_feedback_path()

    def record(self, url: str, relevance_score: int) -> None:
        """Record a relevance score for an article's domain."""
        domain = _extract_domain(url)
        if not domain:
            return

        data = _load_json(self._quality_path)
        data.append({
            "domain": domain,
            "score": relevance_score,
            "timestamp": time.time(),
        })

        # Prune old entries
        cutoff = time.time() - _WINDOW_SECONDS
        data = [d for d in data if d.get("timestamp", 0) > cutoff]
        _save_json(self._quality_path, data)

    def get_boost(self, url: str) -> float:
        """Get a quality boost (0.0-1.0) for a domain based on historical performance.

        Returns 0.0 for unknown domains, up to 1.0 for consistently high-quality domains.
        Applies a penalty if the domain has recent negative feedback.
        """
        domain = _extract_domain(url)
        if not domain:
            return 0.0

        # Check for recent negative feedback
        penalty = self._get_penalty(domain)

        # Calculate average score from history
        data = _load_json(self._quality_path)
        cutoff = time.time() - _WINDOW_SECONDS
        scores = [
            d["score"] for d in data
            if d.get("domain") == domain and d.get("timestamp", 0) > cutoff
        ]

        if not scores:
            return 0.0

        avg = sum(scores) / len(scores)
        # Normalize to 0-1 range (scores are 1-10, so (avg-5)/5 gives -0.8 to 1.0)
        boost = max(0.0, (avg - 5.0) / 5.0)
        return max(0.0, boost - penalty)

    def _get_penalty(self, domain: str) -> float:
        """Check feedback log for recent negative flags on this domain."""
        data = _load_json(self._feedback_path)
        cutoff = time.time() - _FEEDBACK_PENALTY_SECONDS
        recent_flags = [
            d for d in data
            if d.get("domain") == domain
            and d.get("rating") == "down"
            and d.get("timestamp", 0) > cutoff
        ]
        # Each flag in the last 7 days adds 0.2 penalty, capped at 1.0
        return min(1.0, len(recent_flags) * 0.2)

    def record_feedback(self, url: str, rating: str) -> None:
        """Record user feedback (thumbs up/down) for an article's domain."""
        domain = _extract_domain(url)
        if not domain:
            return

        data = _load_json(self._feedback_path)
        data.append({
            "domain": domain,
            "url": url,
            "rating": rating,
            "timestamp": time.time(),
        })
        _save_json(self._feedback_path, data)

    def get_domain_stats(self) -> Dict[str, dict]:
        """Get summary stats for all tracked domains (for debugging/dashboard)."""
        data = _load_json(self._quality_path)
        cutoff = time.time() - _WINDOW_SECONDS

        stats: Dict[str, dict] = {}
        for d in data:
            if d.get("timestamp", 0) <= cutoff:
                continue
            domain = d.get("domain", "")
            if domain not in stats:
                stats[domain] = {"scores": [], "count": 0}
            stats[domain]["scores"].append(d["score"])
            stats[domain]["count"] += 1

        # Compute averages
        for domain, info in stats.items():
            info["avg_score"] = sum(info["scores"]) / len(info["scores"])
            info["boost"] = self.get_boost(f"https://{domain}/")
            del info["scores"]  # Don't expose raw scores

        return stats
