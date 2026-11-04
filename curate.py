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
    soup = fetch(BASE + "/research/")
    out = {}
    for a in soup.select("a[href]"):
        url = article_url(a["href"])
        title = " ".join(a.get_text(" ", strip=True).split())
        if url and len(title) >= 14 and title.lower() not in ("read more", "view more"):
            out[url] = {"title": title[:200], "url": url}
    if not out:
        raise RuntimeError("ISW research listing returned no articles; no new feed will be published")
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
    m = re.search(r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d{1,2},\\s+20\\d{2}", title)
    if m:
        return dateparse.parse(m.group(0)).replace(tzinfo=timezone.utc)
    return None


def gather(now):
    items = []
    for entry in discover()[:35]:
        try:
            soup = fetch(entry["url"])
            title = soup.h1.get_text(" ", strip=True) if soup.h1 else entry["title"]
            dt = published_date(soup, title) or published_date(soup, entry["title"])
            if not dt or not now - timedelta(days=7) <= dt <= now + timedelta(days=1):
                continue
            area = soup.find("main") or soup.find("article") or soup.body
            if not area:
                continue
            for node in area.select("script,style,nav,footer,header,form"):
                node.decompose()
            text = " ".join(area.get_text(" ", strip=True).split())[:4500]
            items.append({"title":title[:200], "url":entry["url"], "date":dt.isoformat(), "text":text})
        except (requests.RequestException, ValueError) as exc:
            print("Skipping ISW page:", entry["url"], str(exc)[:100])
    if not items:
        raise RuntimeError("No recent dated ISW articles verified. Existing published feed remains unchanged.")
    return items


def select(items):
    from openai import OpenAI
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY secret; will not publish uncurated articles")
    prompt = """Tu sélectionnes uniquement les 3 à 5 articles ISW les plus intéressants de la semaine (moins si aucune nouveauté majeure). Critères : changements stratégiques significatifs, cartes vraiment nouvelles, analyse de fond, conséquences géopolitiques. Exclure les répétitions et mises à jour de routine. Ne pas inventer de faits. Réponds uniquement en JSON : {"selected":[{"id":0,"why_fr":"2 phrases originales en français"}]}. Les id doivent provenir des articles transmis."""
    candidates = [{"id":i,"title":x["title"],"date":x["date"],"text":x["text"]} for i,x in enumerate(items)]
    result = OpenAI().chat.completions.create(
        model=os.getenv("OPENAI_MODEL","gpt-4.1-mini"), temperature=0.2,
        response_format={"type":"json_object"},
        messages=[{"role":"system","content":prompt},{"role":"user","content":json.dumps(candidates,ensure_ascii=False)}])
    data = json.loads(result.choices[0].message.content or "{}")
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
        if len(selected) == 5:
            break
    if not selected:
        raise RuntimeError("No usable AI selection; existing feed remains untouched")
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
    (DOCS / "selected.json").write_text(json.dumps(entries,ensure_ascii=False,indent=2) + "\\n",encoding="utf-8")


def main():
    now = datetime.now(timezone.utc)
    current = select(gather(now))
    seen = {x["url"] for x in current}
    for entry in old_entries():
        try:
            dt = datetime.fromisoformat(entry["date"])
            if entry["url"] not in seen and now - timedelta(days=60) <= dt <= now:
                current.append(entry)
                seen.add(entry["url"])
        except (KeyError, ValueError):
            continue
    current.sort(key=lambda x:x["date"],reverse=True)
    publish(current,now)
    print("Published",len(current),"items")


if __name__ == "__main__":
    main()
