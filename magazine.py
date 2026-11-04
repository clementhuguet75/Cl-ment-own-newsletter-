"""Render an original full-length weekly geopolitical article into static HTML and RSS."""
import html
import json
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

DOCS = Path(__file__).parent / "docs"
ROOT_URL = "https://clementhuguet75.github.io/Cl-ment-own-newsletter-"

def e(value):
    return html.escape(str(value or ""),quote=True)

def refs(indices, by_id):
    links = []
    for i in dict.fromkeys(indices or []):
        x = by_id.get(i)
        if x:
            links.append('<a target="_blank" rel="noopener" href="'+e(x["url"])+'">'+e(x["publisher"])+' : '+e(x["title"])+'</a>')
    return " · ".join(links)

def content_html(report, candidates, now):
    ids = {x["id"]:x for x in candidates}
    c = ['<article class="magazine">',
         '<div class="eyebrow">INTELLIGENCE FEED · WEEKLY · '+e(now.strftime("%d/%m/%Y"))+'</div>',
         '<h1>'+e(report["title"])+'</h1>',
         '<p class="subtitle">'+e(report.get("subtitle"))+'</p>',
         '<p class="lead">'+e(report.get("lead"))+'</p>',
         '<section class="quick"><h2>Ce qu’il faut retenir</h2><ul>']
    for sentence in report.get("at_a_glance",[])[:7]:
        c.append("<li>"+e(sentence)+"</li>")
    c.append("</ul></section>")
    for section in report.get("sections",[])[:7]:
        c.append('<section class="chapter"><h2>'+e(section.get("heading"))+'</h2>')
        for p in section.get("body",[])[:7]:
            c.append('<p>'+e(p)+'</p>')
        if section.get("significance"):
            c.append('<p class="insight"><b>Pourquoi c’est important.</b> '+e(section["significance"])+'</p>')
        if section.get("watch"):
            c.append('<p class="insight"><b>À surveiller.</b> '+e(section["watch"])+'</p>')
        c.append('<p class="references"><b>Sources :</b> '+refs(section.get("source_ids",[]),ids)+'</p></section>')
    c.append('<section class="maps"><h2>Les meilleures cartes à consulter</h2>')
    c.append('<p>Nous signalons les cartes pertinentes dans leurs publications originales. Les cartes ISW ne sont pas reproduites ici sans autorisation de réutilisation.</p>')
    for m in report.get("maps",[])[:3]:
        candidate = ids.get(m.get("source_id"))
        if candidate:
            c.append('<div class="map"><b>'+e(m.get("title"))+'</b><p>'+e(m.get("why"))+'</p>'+refs([candidate["id"]],ids)+'</div>')
    c.append('</section><section class="reading"><h2>Pour aller plus loin</h2><ul>')
    for i in report.get("further_reading",[])[:5]:
        if i in ids:
            c.append("<li>"+refs([i],ids)+"</li>")
    c.append('</ul></section>')
    c.append('<div class="method">Ce digest est une synthèse éditoriale originale assistée par IA. Ses analyses et projections sont distinguées des faits documentés. Sources : publications originales créditées dans chaque section. Projet personnel non affilié aux éditeurs cités.</div>')
    c.append("</article>")
    return "\n".join(c)

CSS = """body{background:#f0f2ee;color:#202922;font:17px/1.72 Georgia,serif;margin:0}
main{max-width:760px;min-height:100vh;margin:auto;background:white;padding:45px 28px 90px;box-sizing:border-box}
h1{font-size:43px;line-height:1.13;margin:14px 0;letter-spacing:-.022em}
h2{font:700 25px/1.25 system-ui,sans-serif;margin:1.6em 0 .7em}
.eyebrow{font:700 11px/1.5 system-ui,sans-serif;letter-spacing:.15em;color:#4c7058}
.subtitle{color:#526257;font:20px/1.5 system-ui,sans-serif}.lead{font-size:20px}
.quick{padding:18px 23px;background:#e9f0e9;border-radius:10px;margin:27px 0}
.quick h2{margin:0 0 15px}.quick li{margin:0 0 10px}
.chapter{padding-top:6px;border-top:1px solid #d9ddd9}.insight{border-left:3px solid #8bac91;padding-left:15px}
.references,.maps,.reading,.method{font:13px/1.6 system-ui,sans-serif;color:#536056}
.references{margin-top:22px}.references a,.maps a,.reading a{color:#245e40}
.maps{border-top:1px solid #ddd;margin-top:40px}.map{padding:15px 0;border-bottom:1px solid #eee}
.map>b{color:#203c2b}.method{margin-top:55px;border-top:1px solid #ddd;padding-top:22px}
@media(max-width:600px){main{padding:20px 18px 60px}h1{font-size:32px}body{font-size:16px}}
"""

def page(body,title):
    return '<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+e(title)+'</title><style>'+CSS+'</style></head><body><main>'+body+'</main></body></html>'

def publish(report,candidates,now):
    date = now.date().isoformat()
    article = content_html(report,candidates,now)
    location = DOCS / "weekly" / date
    location.mkdir(parents=True,exist_ok=True)
    (location/"index.html").write_text(page(article,report["title"]),encoding="utf-8")
    (DOCS/"index.html").write_text(page(article,report["title"]),encoding="utf-8")
    manifest_file = DOCS / "editions.json"
    old = json.loads(manifest_file.read_text()) if manifest_file.exists() else []
    edition = {"date":date,"title":report["title"],"subtitle":report.get("subtitle",""),
               "url":ROOT_URL+"/weekly/"+date+"/","article":article}
    all_editions = [edition] + [x for x in old if x.get("date") != date]
    all_editions = all_editions[:12]
    manifest_file.write_text(json.dumps(all_editions,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    ns = "http://purl.org/rss/1.0/modules/content/"
    ET.register_namespace("content",ns)
    root = ET.Element("rss",version="2.0")
    channel = ET.SubElement(root,"channel")
    for tag,text in (("title","Intelligence Feed — Le monde cette semaine"),("link",ROOT_URL+"/"),
                     ("description","Un seul grand digest geopolitique original par semaine"),
                     ("language","fr-FR"),("lastBuildDate",format_datetime(now))):
        ET.SubElement(channel,tag).text=text
    for ed in all_editions:
        item=ET.SubElement(channel,"item")
        for tag,text in (("title",ed["title"]),("link",ed["url"]),("guid",ed["url"]),
                         ("description",ed["article"])):
            ET.SubElement(item,tag).text=text
        stamp = datetime.fromisoformat(ed["date"]).replace(tzinfo=timezone.utc)
        ET.SubElement(item,"pubDate").text=format_datetime(stamp)
        ET.SubElement(item,"{"+ns+"}encoded").text=ed["article"]
    ET.ElementTree(root).write(DOCS/"feed.xml",encoding="utf-8",xml_declaration=True)
    counts={name:sum(x["publisher"]==name for x in candidates) for name in sorted({x["publisher"] for x in candidates})}
    (DOCS/"last_run.json").write_text(json.dumps({"date":now.isoformat(),"scanned":len(candidates),
                     "sources":counts,"sections":len(report["sections"]),"article_url":edition["url"]},
                     ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Weekly digest generated",edition["url"],"from",len(candidates),"candidate articles; publishers",counts)
