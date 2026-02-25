from ai_newsletter_automation.assemble import render_newsletter
from ai_newsletter_automation.models import SummaryItem


def test_render_includes_headlines():
    sections = {
        "indian": [
            SummaryItem(
                Headline="Test Headline",
                Summary_Text="Summary here",
                Live_Link="https://example.com",
            )
        ]
    }
    html = render_newsletter(sections, run_date="2026-02-18")
    assert "Test Headline" in html
    assert "2026-02-18" in html


def test_render_uses_correct_display_names():
    """Section headings must use canonical names, not |title-cased keys."""
    sections = {
        "ai_progress": [
            SummaryItem(
                Headline="Benchmark Win",
                Summary_Text="Summary",
                Live_Link="https://example.com",
            )
        ],
        "research_plain": [
            SummaryItem(
                Headline="New Paper",
                Summary_Text="Summary",
                Live_Link="https://example.com",
            )
        ],
    }
    html = render_newsletter(sections, run_date="2026-02-18")
    assert "AI Progress" in html
    assert "Ai Progress" not in html
    assert "AI Research" in html
    assert "Research Plain" not in html


def test_render_hides_empty_sections():
    """Sections with no items should not appear in the output HTML."""
    sections = {
        "trending": [],
        "indian": [
            SummaryItem(
                Headline="Only Section",
                Summary_Text="Summary",
                Live_Link="https://example.com",
            )
        ],
        "global": [],
    }
    html = render_newsletter(sections, run_date="2026-02-18")
    assert "Indian News" in html
    assert "Trending" not in html
    assert "Global" not in html

