#!/usr/bin/env python3
"""Update existing published editions with licensed in-article contextual maps.
No OpenAI API calls: this republishing is visual only.
"""
import json
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from visuals import enrich_article

DOCS=Path(__file__).parent/"docs"
history_file=DOCS/"editions.json"
history=json.loads(history_file.read_text(encoding="utf-8"))
by_url={}
count=0
for edition in history:
    before=edition["article"]
    after=enrich_article(before)
    if after == before:
        by_url[edition["url"]]=after
        continue
    edition["article"]=after
    by_url[edition["url"]]=after
    target=DOCS/"weekly"/edition["date"]/"index.html"
    original=target.read_text(encoding="utf-8")
    if before not in original:
        raise RuntimeError("Could not find the old article HTML in "+str(target))
    target.write_text(original.replace(before,after,1),encoding="utf-8")
    count+=1

if not count:
    print("No published articles require additional maps.")
else:
    history_file.write_text(json.dumps(history,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    latest=history[0]
    home=DOCS/"index.html"
    contents=home.read_text(encoding="utf-8")
    # The edition's title may be different from the homepage; only replace main contents.
    pos1=contents.find("<main>")
    pos2=contents.find("</main>",pos1)
    if pos1<0 or pos2<0:
        raise RuntimeError("Unexpected homepage format")
    home.write_text(contents[:pos1+6]+latest["article"]+contents[pos2:],encoding="utf-8")
    rss=DOCS/"feed.xml"
    tree=ET.parse(rss)
    root=tree.getroot()
    channel=root.find("channel")
    for item in channel.findall("item"):
        link=item.findtext("link")
        if link not in by_url:
            continue
        for name in ("description","{http://purl.org/rss/1.0/modules/content/}encoded"):
            el=item.find(name)
            if el is not None:
                el.text=by_url[link]
    d=channel.find("lastBuildDate")
    if d is not None:
        d.text=format_datetime(datetime.now(timezone.utc))
    ET.register_namespace("content","http://purl.org/rss/1.0/modules/content/")
    tree.write(rss,xml_declaration=True,encoding="utf-8")
    print("Updated",count,"editions; added inline licensed map figures")
