from ai_newsletter_automation.verify import is_paywalled


def test_paywall_detection_simple():
    html = "<html><body>Subscribe to read this article</body></html>"
    assert is_paywalled(html) is True


def test_paywall_detection_allows_free():
    html = "<html><body>This article is free to read</body></html>"
    assert is_paywalled(html) is False

