"""LLM-as-Judge pre-reranking — scores article relevance before summarization."""

import json
import logging
import time
from typing import List, Optional
import groq

import requests

from .config import get_settings
from .models import VerifiedArticle, SectionConfig

log = logging.getLogger(__name__)

_RERANK_SYSTEM = (
    "You are a relevance-scoring assistant. You will receive a section topic and a "
    "numbered list of article titles and snippets. For EACH article, return a JSON "
    "array of objects with keys: {\"index\": <int>, \"score\": <1-10>}.\n"
    "Score meaning:\n"
    "  1-3: Off-topic, clickbait, rumors, or very low relevance\n"
    "  4-5: Tangentially related or old news being reposted\n"
    "  6-7: Relevant and recent\n"
    "  8-10: Highly relevant, empirical results, or official announcements\n"
    "CRITICAL: You must return the array wrapped in a JSON object with a single key 'items'. Do not return just a raw array."
)


def _build_rerank_prompt(section_name: str, articles: List[VerifiedArticle]) -> str:
    lines = [f"Section topic: {section_name}\n\nArticles:"]
    for i, a in enumerate(articles):
        # Use up to 2000 chars of content for better judgement
        snippet = (a.content or a.snippet or "")[:2000]
        # Clean up newlines for the prompt
        snippet = snippet.replace("\n", " ")
        date_str = a.scraped_published_date or a.published or "Unknown"
        lines.append(f"{i+1}. Title: {a.title}\n   Date: {date_str}\n   Snippet: {snippet}...")
    return "\n".join(lines)


def _parse_scores(raw: str, count: int) -> List[int]:
    """Parse LLM JSON response into a list of scores aligned by article index."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    data = json.loads(cleaned)
    if isinstance(data, dict) and "items" in data:
        data = data["items"]
        
    scores = [5] * count  # default score for any missing entries
    for obj in data:
        idx = int(obj.get("index", 0)) - 1  # 1-indexed → 0-indexed
        if 0 <= idx < count:
            scores[idx] = int(obj.get("score", 5))
    return scores


def rerank_articles(
    articles: List[VerifiedArticle],
    section: SectionConfig,
    model: str = "llama-3.3-70b-versatile",
) -> List[VerifiedArticle]:
    """Score and filter articles by LLM-judged relevance.

    Only invoked when len(articles) > section.limit to avoid wasting tokens.
    On any error, returns articles unchanged (graceful fallback).
    """
    if len(articles) <= section.limit:
        return articles

    settings = get_settings()
    # Configure Groq
    if "gemini" in model or "llama-3." in model or "llama3" in model:
        model = "llama-3.3-70b-versatile"
        
    client = groq.Groq(api_key=settings.groq_api_key)
    
    prompt = _build_rerank_prompt(section.name, articles)
    
    try:
        raw = ""
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": _RERANK_SYSTEM},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                raw = response.choices[0].message.content
                break
            except groq.APIError:
                if attempt == 2:
                    raise
                time.sleep(2 * (2 ** attempt))
                
        scores = _parse_scores(raw, len(articles))
    except Exception as e:
        log.warning("Reranking failed, returning articles unchanged: %s", e)
        return articles

    # Pair articles with scores, filter below threshold, sort descending
    scored = list(zip(articles, scores))
    scored = [(a, s) for a, s in scored if s >= section.relevance_threshold]
    scored.sort(key=lambda x: x[1], reverse=True)

    result = [a for a, _ in scored]
    log.info(
        "Reranked %d → %d articles for '%s' (threshold=%d)",
        len(articles), len(result), section.name, section.relevance_threshold,
    )
    return result
