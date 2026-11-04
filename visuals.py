"""Verified freely reusable CONTEXT maps embedded directly in the article/RSS.

These are geographic context maps, NOT live frontline maps.
ISW operational maps are copyrighted and must not be copied into derivative
analytical products without ISW's written permission.
"""
import html
import re

MAPS = [
    {
      "key":"ukraine",
      "match":r"\b(ukraine|ukrainien|ukrainienne|kyiv|kiev|donbass|crimée|crimée|moscou|russie)\b",
      "src":"https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Political_Map_of_Ukraine.svg/1024px-Political_Map_of_Ukraine.svg.png",
      "title":"Ukraine — carte géographique de référence",
      "caption":"Carte politique générale (2025), sans indication de la ligne de front ni des changements militaires de la semaine.",
      "author":"Athosmera",
      "licence":"CC0 1.0",
      "licence_url":"https://creativecommons.org/publicdomain/zero/1.0/",
      "page":"https://commons.wikimedia.org/wiki/File:Political_Map_of_Ukraine.svg",
    },
    {
      "key":"middleeast",
      "match":r"\b(iran|isra[eë]l|moyen.orient|liban|syrie|irak|gaza|golfe persique|iranien)\b",
      "src":"https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/Middle_East_topographic_map.png/1280px-Middle_East_topographic_map.png",
      "title":"Moyen-Orient — relief et géographie stratégique",
      "caption":"Carte topographique de contexte (2017). Elle ne représente pas les combats, les frontières contestées ni les opérations actuelles.",
      "author":"Joe Roe",
      "licence":"CC BY-SA 4.0",
      "licence_url":"https://creativecommons.org/licenses/by-sa/4.0/",
      "page":"https://commons.wikimedia.org/wiki/File:Middle_East_topographic_map.png",
    },
    {
      "key":"taiwan",
      "match":r"\b(ta[iï]wan|détroit de ta[iï]wan|taipei)\b",
      "src":"https://upload.wikimedia.org/wikipedia/commons/thumb/1/15/LocationTaiwan.svg/960px-LocationTaiwan.svg.png",
      "title":"Taïwan — situation géographique",
      "caption":"Carte de contexte (2009), sans représentation des opérations militaires ni des changements territoriaux récents.",
      "author":"Keepscases",
      "licence":"Domaine public",
      "licence_url":"https://commons.wikimedia.org/wiki/File:LocationTaiwan.svg",
      "page":"https://commons.wikimedia.org/wiki/File:LocationTaiwan.svg",
    },
]

def escape(text):
    return html.escape(str(text or ""),quote=True)

def figure(asset):
    title = escape(asset["title"])
    return ('<figure class="visual-map">'
            '<img src="'+escape(asset["src"])+'" alt="'+title+'" loading="lazy" '
            'style="display:block;width:100%;max-width:100%;height:auto" />'
            '<figcaption><strong>'+title+'</strong> — '+escape(asset["caption"])+' '
            'Source : <a href="'+escape(asset["page"])+'">'+escape(asset["author"])+'</a> '
            '(<a href="'+escape(asset["licence_url"])+'">'+escape(asset["licence"])+'</a>).</figcaption>'
            '</figure>')

def enrich_article(fragment):
    """Add context visuals into matching sections, max 3, without duplicating images."""
    if 'class="visual-map"' in fragment:
        return fragment
    used = set()
    chunks = re.split(r'(<section class="chapter">)',fragment)
    rendered = []
    for n,part in enumerate(chunks):
        if part != '<section class="chapter">':
            if rendered and rendered[-1] == '<section class="chapter">':
                heading = re.search(r'<h2>(.*?)</h2>',part,re.S)
                if heading:
                    heading_text = html.unescape(re.sub('<[^>]+>',' ',heading.group(1))).lower()
                    for asset in MAPS:
                        if asset['key'] not in used and re.search(asset['match'],heading_text,re.I):
                            end=heading.end()
                            part=part[:end]+figure(asset)+part[end:]
                            used.add(asset['key'])
                            break
            rendered.append(part)
        else:
            rendered.append(part)
    return "".join(rendered)
