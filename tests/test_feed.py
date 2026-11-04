"""Unit tests for original multi-source weekly digest and embedded full-content RSS."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
import magazine
from sources import allowed, date_for

class IntelligenceFeedTests(unittest.TestCase):
    def test_url_allowlist(self):
        self.assertTrue(allowed("https://understandingwar.org/research/russia-ukraine/example/","understandingwar.org"))
        self.assertFalse(allowed("https://fake-understandingwar.org/research/example/","understandingwar.org"))

    def test_dates(self):
        now = datetime(2026,11,4,12,tzinfo=timezone.utc)
        self.assertEqual(date_for("Russia Update, November 3, 2026","",now).date().isoformat(),"2026-11-03")
        self.assertEqual(date_for("An analysis","about 2 days ago",now).date().isoformat(),"2026-11-02")

    def test_full_html_inside_rss(self):
        now = datetime(2026,11,4,12,tzinfo=timezone.utc)
        entries = [{"id":0,"title":"Ukraine report","publisher":"ISW","url":"https://understandingwar.org/research/russia-ukraine/ukraine-report/","date":now.isoformat(),"excerpt":"Update"}]
        report = {"title":"Le monde cette semaine","subtitle":"Une synthèse","lead":"Un vrai éditorial original",
                  "at_a_glance":["Point important"],
                  "sections":[{"heading":"Ukraine","body":["Texte analytique complet"],"source_ids":[0],"significance":"Enjeu","watch":"Suite"}],
                  "maps":[{"title":"Carte originale","why":"Repères","source_id":0}],"further_reading":[0]}
        original = magazine.DOCS
        with tempfile.TemporaryDirectory() as tmp:
            magazine.DOCS = Path(tmp)
            try:
                magazine.publish(report,entries,now)
                root = ET.parse(Path(tmp)/"feed.xml").getroot()
                items = root.findall("channel/item")
                self.assertEqual(len(items),1)
                body = items[0].find("{http://purl.org/rss/1.0/modules/content/}encoded").text
                self.assertIn("Texte analytique complet",body)
                self.assertIn("understandingwar.org",body)
                self.assertTrue((Path(tmp)/"weekly/2026-11-04/index.html").exists())
            finally:
                magazine.DOCS = original

if __name__ == "__main__":
    unittest.main()
