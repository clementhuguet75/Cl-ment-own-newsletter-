#!/usr/bin/env python3
"""Produce a curated RSS feed pointing to original ISW articles, never copying maps."""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparse

BASE = "https://understandingwar.org"
ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; personal intelligence feed)"}


def article_url(href):
    u = urlparse(urljoin(BASE, href))
    segments = [part for part in u.path.split("/") if part]
    if u.scheme != "https" or u.hostname not in ("understandingwar.org", "www.understandingwar.org"):
        return None
    if len(segments) < 3 or segments[0] != "research":
        return None
    return BASE + "/" + "/".join(segments) + "/"


def fetch(url):
    r = requests.get(url, timeout=25, headers=HEADERS)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def discover():
    out = {}
    errors = []
    # ISW rejects requests from some hosted servers (Cloudflare 403).
    # Feeder publicly lists direct original links and short metadata snippets.
    for listing in (BASE + "/research/", BASE + "/", "https://feeder.co/discover/fbbae6245c/understandingwar-org"):
        try:
            soup = fetch(listing)
        except requests.RequestException as exc:
            errors.append(str(exc)[:150])
            continue
        links = soup.select("a.discover-feed-item-link[href]") if "feeder.co" in listing else soup.select("a[href]")
        for a in links:
            url = article_url(a["href"])
            title = " ".join(a.get_text(" ", strip=True).split())
            if not url or len(title) < 14 or title.lower() in ("read more", "view more"):
                continue
            meta = ""
            if "feeder.co" in listing:
                container = a.find_parent("div", class_="flex-grow-1")
                desc = container.select_one("p.card-text") if container else None
                meta = desc.get_text(" ", strip=True)[:500] if desc else ""
            if url not in out:
                out[url] = {"title": title[:200], "url": url, "summary": meta}
    if not out:
        raise RuntimeError("No ISW article links discovered. Listing errors: " + " | ".join(errors))
    return list(out.values())[:45]

def published_date(soup, title):
    for attrs in ({"property":"article:published_time"},{"name":"date"},{"name":"datePublished"},{"itemprop":"datePublished"}):
        node = soup.find("meta", attrs=attrs)
        if node and node.get("content"):
            try:
                dt = dateparse.parse(node["content"])
                return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
            except (ValueError, TypeError, OverflowError):
                pass
    for node in soup.select("time[datetime]"):
        try:
            dt = dateparse.parse(node["datetime"])
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        except (ValueError, TypeError, OverflowError):
            pass
    m = re.search(r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}", title)
    if m:
        return dateparse.parse(m.group(0)).replace(tzinfo=timezone.utc)
    return None


def gather(now):
    items = []
    blocked = False
    for entry in discover()[:35]:
        # Published date must be verifiable; never fabricate publication dates.
        title = entry["title"]
        dt = published_date(BeautifulSoup("", "html.parser"), title)
        text = entry.get("summary", "")
        if not dt or not now - timedelta(days=7) <= dt <= now + timedelta(days=1):
            continue
        if not blocked:
            try:
                soup = fetch(entry["url"])
                title = soup.h1.get_text(" ", strip=True) if soup.h1 else title
                dt = published_date(soup, title) or dt
                area = soup.find("main") or soup.find("article") or soup.body
                if area:
                    for node in area.select("script,style,nav,footer,header,form"):
                        node.decompose()
                    text = " ".join(area.get_text(" ", strip=True).split())[:4500]
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code in (403, 429):
                    blocked = True
                print("Article retrieval restricted; using indexed metadata only:", str(exc)[:100])
            except requests.RequestException as exc:
                print("Article temporarily unavailable; using indexed metadata:", str(exc)[:100])
        items.append({"title":title[:200], "url":entry["url"], "date":dt.isoformat(), "text":text})
    if not items:
        raise RuntimeError("No recent dated ISW articles verified; preserving existing feed")
    return items

def select(items, max_new=1):
    from openai import OpenAI
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not available to this workflow. Verify the repository Actions secret name.")
    # Source site may return 403 from GitHub. A web-grounded model must research
    # the actual content, not infer importance from generic article titles.
    prompt = """Tu es un rédacteur en chef spécialisé en géopolitique. Examine les liens ISW fournis et recherche sur le web les faits saillants de ces rapports lorsqu'ils sont disponibles.
Sélectionne uniquement les analyses apportant une évolution MAJEURE, une carte nouvelle significative, ou une analyse stratégique de fond.
Ne publie pas une analyse juste parce qu'elle a été publiée. Si les rapports ne sont pas suffisamment vérifiables, ne sélectionne rien.
Réponse exclusivement en JSON {"selected":[{"id":0,"why_fr":"Une ou deux phrases factuelles, fiables et originales en français"}]}. Utilise seulement les id fournis. Maximum un contenu sélectionné pour cette édition quotidienne. Évite les généralisations, détails invérifiables et doublons."""
    candidates = [{"id":i,"title":x["title"],"date":x["date"],"url":x["url"],"summary":x["text"][:750]} for i,x in enumerate(items)]
    answer = OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL","gpt-4.1-mini"),
        tools=[{"type":"web_search","search_context_size":"medium"}],
        input=[{"role":"system","content":prompt},{"role":"user","content":json.dumps(candidates,ensure_ascii=False)}])
    raw = (answer.output_text or "").strip()
    found = re.search(r"\\{[\\s\\S]*\\}", raw)
    if not found:
        raise RuntimeError("AI response was not valid JSON; keeping previously published feed")
    data = json.loads(found.group(0))
    selected, seen = [], set()
    for row in data.get("selected", []):
        try:
            idx = int(row["id"])
            note = str(row["why_fr"]).strip()
        except (KeyError, ValueError, TypeError):
            continue
        if idx in seen or not 0 <= idx < len(items) or not note:
            continue
        seen.add(idx)
        selected.append({k:items[idx][k] for k in ("title","url","date")} | {"why_fr":note[:500]})
        if len(selected) == max_new:
            break
    return selected

def old_entries():
    repo = os.getenv("GITHUB_REPOSITORY","")
    old = []
    if "/" in repo:
        owner, name = repo.split("/",1)
        try:
            r = requests.get("https://" + owner + ".github.io/" + name + "/feed.xml", timeout=15)
            if r.ok:
                root = ET.fromstring(r.content)
                for item in root.findall("channel/item"):
                    url = item.findtext("link")
                    if url and article_url(url):
                        old.append({"url":url,"title":item.findtext("title") or "",
                                    "date":parsedate_to_datetime(item.findtext("pubDate")).astimezone(timezone.utc).isoformat(),
                                    "why_fr":item.findtext("description") or ""})
        except (requests.RequestException, ET.ParseError, ValueError, TypeError):
            pass
    if not old:
        old = json.loads((DOCS / "selected.json").read_text())
    return old


def publish(entries, now):
    rss = ET.Element("rss",version="2.0")
    ch = ET.SubElement(rss,"channel")
    for tag,value in (("title","ISW | Intelligence Feed - Selection"),("link",BASE + "/"),
                      ("description","Analyses ISW majeures, selectionnees chaque semaine"),
                      ("language","fr-FR"),("lastBuildDate",format_datetime(now))):
        ET.SubElement(ch,tag).text = value
    for entry in entries[:45]:
        node = ET.SubElement(ch,"item")
        for tag,value in (("title",entry["title"]),("link",entry["url"]),
                          ("description",entry["why_fr"]),("pubDate",format_datetime(datetime.fromisoformat(entry["date"])))):
            ET.SubElement(node,tag).text = value
        ET.SubElement(node,"guid",isPermaLink="true").text = entry["url"]
    DOCS.mkdir(exist_ok=True)
    ET.ElementTree(rss).write(DOCS / "feed.xml",encoding="utf-8",xml_declaration=True)
    (DOCS / "selected.json").write_text(json.dumps(entries,ensure_ascii=False,indent=2) + "\n",encoding="utf-8")


def main():
    now = datetime.now(timezone.utc)
    old = old_entries()
    # Feed is populated gradually through the week: at most 5 each ISO week.
    week = now.isocalendar()[:2]
    used = sum(1 for x in old if datetime.fromisoformat(x["date"]).isocalendar()[:2] == week)
    existing_urls = {x["url"] for x in old}
    slots = max(0, 5 - used)
    fresh = []
    if slots:
        fresh = [x for x in gather(now) if x["url"] not in existing_urls]
    new = select(fresh, max_new=1) if fresh and slots else []
    current = new + [x for x in old if now - timedelta(days=60) <= datetime.fromisoformat(x["date"]) <= now]
    # Publishing 0 articles is legitimate; never insert filler or demo items.
    current.sort(key=lambda x:x["date"],reverse=True)
    publish(current,now)
    print("Published",len(current),"articles; added",len(new),"new articles")

if __name__ == "__main__":
    main()
