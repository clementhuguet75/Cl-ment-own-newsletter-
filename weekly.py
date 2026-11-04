#!/usr/bin/env python3
"""Research many source items and publish ONE substantial weekly geopolitical digest."""
import json
import os
import re
from datetime import datetime, timezone
from openai import OpenAI
from sources import collect
from magazine import publish

EDITORIAL_RULES = """
Tu es le rédacteur en chef d'un journal géopolitique personnel premium en FRANÇAIS.
À partir de dizaines de liens d'analyses ISW, CSIS, CFR, RUSI et ECFR, tu dois RÉDIGER UN SEUL NOUVEL ARTICLE DE SYNTHESE, PAS une liste d'articles retenus. Tu peux utiliser web_search pour approfondir et recouper les faits.
Objectif : 10 à 15 minutes de lecture, si la matière le justifie. Ton éditorial, précis, hiérarchisé, riche et pédagogique. Fais émerger les dynamiques qui relient les événements, les conséquences et les incertitudes. 4 à 6 grands dossiers; chaque dossier comporte 3 à 5 paragraphes développés, un enjeu stratégique, et ce qu'il faudra suivre.
Les faits doivent être datés précisément. N'interprète pas une restriction ou une crise temporaire déjà résolue comme une situation toujours en cours. Toute évolution antérieure à la semaine peut être utilisée comme contexte, mais pas présentée comme une nouveauté. Vérifie si des événements annoncés ont été démentis, clos ou modifiés avant publication. Distingue événements confirmés, estimations d'analystes et hypothèses. Pas de fausses citations ni chiffres inventés. Les liens fournis sont souvent des résumés, pas les textes complets. N'affirme jamais avoir lu un texte non accessible. Si une information ne peut être corroborée, ne la formule pas comme un fait.
Toutes les références doivent pointer vers les URLs originales dans le corpus. Les id doivent correspondre aux articles fournis. Chaque dossier doit comporter au moins 2 références si possible. Assure-toi que chaque référence traite réellement des affirmations de son dossier, et non pas uniquement d'un sujet voisin. Tu peux utiliser la recherche web pour vérifier les détails des rapports.
Pour les meilleures cartes : sélectionne au maximum 3 rapports originaux contenant des cartes vraisemblablement pertinentes; explique leur intérêt mais ne reproduis pas les images ISW, dont l'incorporation dans d'autres publications demande une permission. Pas de fausses cartes.
Format de sortie : JSON valide uniquement, sans markdown. Schéma :
{
 "title": "titre éditorial original",
 "subtitle": "ce que cette semaine nous apprend",
 "lead": "2 paragraphes courts de mise en perspective",
 "at_a_glance": ["cinq à sept phrases rédigées"],
 "sections":[
   {"heading":"un titre analytique","body":["paragraphe développé","paragraphe développé","paragraphe développé","paragraphe développé"],
    "significance":"le véritable enjeu stratégique",
    "watch":"les signaux ou événements à surveiller",
    "source_ids":[0,12]}
 ],
 "maps":[{"title":"carte / rapport","why":"ce que cette carte permet de comprendre","source_id":3}],
 "further_reading":[3,8,12]
}
Ne pas sélectionner une seule analyse; FAIRE LA SYNTHESE de toutes les actualités matérielles pertinentes. Ignorer les publications de routine. Placer une référence par dossier, pas des références fabriquées. Les sources qui ne sont pas utiles n'ont pas besoin d'être citées.
"""

def make_digest(candidates, now):
    compact = [{"id":a["id"],"publisher":a["publisher"],"date":a["date"][:10],
                "title":a["title"],"url":a["url"],"excerpt":a["excerpt"][:420]}
               for a in candidates]
    response = OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
        tools=[{"type":"web_search","search_context_size":"medium"}],
        max_output_tokens=7500,
        input=[
            {"role":"system","content":EDITORIAL_RULES},
            {"role":"user","content":"Date UTC : "+now.date().isoformat()+"; corpus de "+str(len(compact))+
             " publications des 7 derniers jours :\n"+json.dumps(compact,ensure_ascii=False)}
        ])
    print("Usage:", response.usage)
    raw = (response.output_text or "").strip()
    if raw.startswith("~~~"):
        raw = re.sub(r"^~~~(?:json)?\s*|\s*~~~$", "", raw, flags=re.I)
    try:
        digest = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}",raw,re.S)
        if not match:
            raise RuntimeError("Model did not return a JSON digest")
        digest=json.loads(match.group())
    if not isinstance(digest,dict) or len(digest.get("sections",[])) < 3:
        raise RuntimeError("Digest too short: preserving previous edition")
    allowed = {a["id"] for a in candidates}
    for section in digest["sections"]:
        refs = section.get("source_ids",[])
        if not isinstance(refs,list) or not refs or any(i not in allowed for i in refs):
            raise RuntimeError("Some editorial references do not match verified candidate articles")
        if not section.get("body"):
            raise RuntimeError("Empty analysis section")
    for card in digest.get("maps",[]):
        if card.get("source_id") not in allowed:
            raise RuntimeError("Invalid map source")
    for i in digest.get("further_reading",[]):
        if i not in allowed:
            raise RuntimeError("Invalid further reading source")
    return digest


def audit_digest(digest, candidates, now):
    """Second editorial pass: verify dates and factual assertions before public publication."""
    source_index = [{"id":x["id"],"title":x["title"],"publisher":x["publisher"],
                     "date":x["date"][:10],"url":x["url"]} for x in candidates]
    prompt = """Tu es le fact-checker de la revue Intelligence Feed. Tu dois réviser le BROUILLON géopolitique fourni. Vérifie activement, avec la recherche web, les principales affirmations factuelles datées : la chronologie, le caractère temporaire ou résolu d'un incident, les dates d'ouverture d'installations militaires, le statut des élections, les personnes, les capacités militaires, et la correspondance avec les articles cités.
Élimine ou nuance toute affirmation non corroborée. N'écris PAS au présent une restriction déjà levée. Ne présente PAS un événement de septembre ou octobre comme une nouveauté de novembre. Attention à la différence entre les preuves accessibles et les hypothèses d'analystes. Les sources du corpus sont des liens, parfois seulement un extrait; ne prétends pas avoir vérifié des détails que tu ne peux pas confirmer.
Retourne uniquement le même objet JSON, conservant la structure et l'essentiel de la profondeur analytique : title, subtitle, lead, at_a_glance, sections (heading, body, significance, watch, source_ids), maps (title, why, source_id), further_reading. Chaque source_id doit appartenir à la liste. N'ajoute pas de fait nouveau sans source appropriée. Corrige toute erreur détectée sans embellir."""
    resp = OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
        tools=[{"type":"web_search","search_context_size":"medium"}],
        max_output_tokens=7500,
        input=[
            {"role":"system","content":prompt},
            {"role":"user","content":"Date : "+now.date().isoformat()+"\nSOURCES DISPONIBLES : "+
             json.dumps(source_index,ensure_ascii=False)+
             "\nARTICLE A AUDITER : "+json.dumps(digest,ensure_ascii=False)}
        ])
    print("Fact check usage:",resp.usage)
    raw=(resp.output_text or "").strip()
    try:
        audited=json.loads(raw)
    except json.JSONDecodeError:
        match=re.search(r"\{.*\}",raw,re.S)
        if not match:
            raise RuntimeError("Fact-check did not return valid JSON; preserving previous issue")
        audited=json.loads(match.group())
    allowed={x["id"] for x in candidates}
    sections=audited.get("sections",[])
    if len(sections)<3:
        raise RuntimeError("Fact check produced too few sections")
    for section in sections:
        references=section.get("source_ids",[])
        if not isinstance(references,list) or not references or any(i not in allowed for i in references):
            raise RuntimeError("Fact-check returned invalid references")
        if not section.get("body"):
            raise RuntimeError("Fact check returned an empty section")
    for item in audited.get("maps",[]):
        if item.get("source_id") not in allowed:
            raise RuntimeError("Fact check returned a map with an invalid source")
    return audited


def main():
    now = datetime.now(timezone.utc)
    candidates = collect(now)
    report = make_digest(candidates,now)
    checked = audit_digest(report,candidates,now)
    publish(checked,candidates,now)

if __name__ == "__main__":
    main()
