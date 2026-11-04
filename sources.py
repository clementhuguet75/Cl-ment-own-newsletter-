"""Collect original links and dated summaries from reputable geopolitical publications."""
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

HEADERS = {"User-Agent": "IntelligenceFeed/1.0 (personal noncommercial research)"}
FEEDER = [
    ("ISW", "https://feeder.co/discover/fbbae6245c/understandingwar-org", "understandingwar.org"),
    ("CSIS", "https://feeder.co/discover/da4a7c44f4/csis-org-analysis", "csis.org"),
    ("CFR", "https://feeder.co/discover/66c126d694/cfr-org", "cfr.org"),
]
RSS = [
    ("RUSI", "https://www.rusi.org/rss/latest-publications.xml", "rusi.org"),
    ("ECFR", "https://ecfr.eu/feed/?post_type=post", "ecfr.eu"),
    ("ECFR", "https://ecfr.eu/feed/?post_type=publication", "ecfr.eu"),
]

def fetch(url):
    response = requests.get(url, headers=HEADERS, timeout=22)
    response.raise_for_status()
    return response.text

def clean(value):
    return " ".join(BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True).split())

def allowed(url, domain):
    p = urlparse(url)
    return p.scheme == "https" and p.hostname in (domain, "www." + domain)

def date_for(title, relative, now):
    match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}", title, re.I)
    if match:
        return dateparser.parse(match.group()).replace(tzinfo=timezone.utc)
    label = (relative or "").lower()
    if "yesterday" in label:
        return now - timedelta(days=1)
    if "today" in label or "just now" in label:
        return now
    m = re.search(r"(\d+)\s*(minute|hour|day|week|month)", label)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    if unit == "minute":
        return now - timedelta(minutes=n)
    if unit == "hour":
        return now - timedelta(hours=n)
    return now - timedelta(days=n * (30 if unit == "month" else 7 if unit == "week" else 1))

def feeder(name, url, domain, now):
    soup = BeautifulSoup(fetch(url), "html.parser")
    out = []
    for a in soup.select("a.discover-feed-item-link[href]"):
        link = a["href"].split("#")[0]
        title = clean(a.get_text(" ", strip=True))
        if not allowed(link, domain) or len(title) < 12:
            continue
        parent = a.find_parent("div", class_="flex-grow-1")
        rel = parent.select_one("small.text-muted") if parent else None
        summ = parent.select_one("p.card-text") if parent else None
        dt = date_for(title, rel.get_text(" ", strip=True) if rel else "", now)
        if dt:
            out.append({"publisher":name, "title":title[:220], "url":link,
                        "date":dt.isoformat(), "excerpt":clean(str(summ))[:500]})
    return out[:35]

def rss(name, url, domain):
    root = ET.fromstring(fetch(url))
    out = []
    for item in list(root.findall(".//item")) + list(root.findall(".//{http://www.w3.org/2005/Atom}entry")):
        def value(tag):
            node = item.find(tag)
            return (node.text or "").strip() if node is not None else ""
        title = clean(value("title") or value("{http://www.w3.org/2005/Atom}title"))
        link = value("link")
        if not link:
            node = item.find("{http://www.w3.org/2005/Atom}link")
            link = node.get("href","") if node is not None else ""
        if not allowed(link, domain):
            continue
        rawdate = value("pubDate") or value("{http://purl.org/dc/elements/1.1/}date") or value("{http://www.w3.org/2005/Atom}updated")
        try:
            dt = dateparser.parse(rawdate)
            dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        except (ValueError, TypeError, OverflowError):
            continue
        excerpt = value("description") or value("{http://www.w3.org/2005/Atom}summary")
        out.append({"publisher":name,"title":title[:220],"url":link.split("#")[0],
                    "date":dt.isoformat(),"excerpt":clean(excerpt)[:500]})
    return out[:35]

def collect(now):
    results = []
    for name,url,domain in FEEDER + RSS:
        try:
            items = feeder(name,url,domain,now) if (name,url,domain) in FEEDER else rss(name,url,domain)
            results += items
            print("Source:",name,"candidate links:",len(items))
        except Exception as exc:
            print("Source unavailable:",name,str(exc)[:140])
    unique = {}
    since = now - timedelta(days=7)
    for x in results:
        dt = datetime.fromisoformat(x["date"])
        if since <= dt <= now + timedelta(days=1):
            unique.setdefault(x["url"].rstrip("/"),x)
    chosen = sorted(unique.values(),key=lambda x:x["date"],reverse=True)[:100]
    for i,x in enumerate(chosen):
        x["id"] = i
    print("Total unique candidates:",len(chosen),"sources:",sorted(set(x["publisher"] for x in chosen)))
    if len(chosen) < 8 or len({x["publisher"] for x in chosen}) < 2:
        raise RuntimeError("Insufficient recent articles across multiple sources: no digest will be published")
    return chosen
