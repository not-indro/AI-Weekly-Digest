
import unittest
from ai_newsletter_automation.scrape import extract_metadata

class TestScrapeMetadata(unittest.TestCase):
    def test_meta_tag_standard(self):
        html = """
        <html>
            <head>
                <meta property="article:published_time" content="2023-10-27T10:00:00Z" />
            </head>
            <body></body>
        </html>
        """
        meta = extract_metadata(html)
        self.assertEqual(meta.get("date"), "2023-10-27T10:00:00Z")

    def test_meta_tag_name(self):
        html = """
        <html>
            <head>
                <meta name="pubdate" content="2023-10-26" />
            </head>
        </html>
        """
        meta = extract_metadata(html)
        self.assertEqual(meta.get("date"), "2023-10-26")

    def test_json_ld(self):
        html = """
        <html>
            <head>
                <script type="application/ld+json">
                {
                    "@context": "https://schema.org",
                    "@type": "NewsArticle",
                    "headline": "AI is cool",
                    "datePublished": "2023-10-25T09:30:00+00:00"
                }
                </script>
            </head>
        </html>
        """
        meta = extract_metadata(html)
        self.assertEqual(meta.get("date"), "2023-10-25T09:30:00+00:00")

    def test_time_tag(self):
        html = """
        <html>
            <body>
                <h1>Title</h1>
                <time datetime="2023-10-24">Oct 24, 2023</time>
            </body>
        </html>
        """
        meta = extract_metadata(html)
        self.assertEqual(meta.get("date"), "2023-10-24")

if __name__ == "__main__":
    unittest.main()
