import unittest
from xml.etree import ElementTree as ET
from pathlib import Path
from bs4 import BeautifulSoup
from curate import article_url, published_date

class FeedTests(unittest.TestCase):
    def test_original_links(self):
        self.assertEqual(article_url("/research/russia-ukraine/sample-report/"),"https://understandingwar.org/research/russia-ukraine/sample-report/")
        self.assertIsNone(article_url("https://example.com/research/a/b/"))
    def test_title_date(self):
        self.assertEqual(published_date(BeautifulSoup("<html></html>","html.parser"),"Iran Update, November 3, 2026").date().isoformat(),"2026-11-03")
    def test_empty_initial_feed(self):
        root=ET.parse(Path(__file__).parents[1] / "docs/feed.xml").getroot()
        self.assertEqual(root.tag,"rss")
        self.assertEqual(len(root.findall("channel/item")),0)

if __name__=="__main__":
    unittest.main()
