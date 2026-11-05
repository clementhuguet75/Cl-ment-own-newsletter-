#!/usr/bin/env python3
"""Research many source items and publish ONE substantial weekly geopolitical digest."""
import json
import os
import re
from datetime import datetime, timezone
from openai import OpenAI
from sources import collect
from magazine import publish

# Strict output shape: prevents occasional malformed editorial JSON responses.
DIGEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "lead": {"type": "string"},
        "at_a_glance": {"type": "array", "items": {"type": "string"}},
        "sections": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "heading": {"type": "string"},
                    "body": {"type": "array", "items": {"type": "string"}},
                    "significance": {"type": "string"},
                    "watch": {"type": "string"},
                    "source_ids": {"type": "array", "items": {"type": "integer"}}
                },
                "required": ["heading", "body", "significance", "watch", "source_ids"]
            }
        },
        "maps": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "why": {"type": "string"},
                    "source_id": {"type": "integer"}
                },
                "required": ["title", "why", "source_id"]
            }
        },
        "further_reading": {"type": "array", "items": {"type": "integer"}}
    },
    "required": ["title", "subtitle", "lead", "at_a_glance", "sections", "maps", "further_reading"]
}

EDITORIAL_RULES = """
Tu es le rédacteur en chef d'un journal géopolitique personnel premium en FRANÇAIS.
À partir de dizaines de liens d'analyses ISW, CSIS, CFR, RUSI et ECFR, tu dois RÉDIGER UN SEUL NOUVEL ARTICLE DE SYNTHESE, PAS une liste d'articles retenus. Tu peux utiliser web_search pour approfondir et recouper les faits.
Objectif : 10 à 15 minutes de lecture, avec 3 à 4 dossiers PLUS PROFONDS plutôt que 5 à 6 dossiers superficiels. Style d'un analyste OSINT pédagogique : précis, factuel, concret, sobre, accessible. Rédige d'abord les faits, puis explique leur portée. ÉVITE les formules abstraites et pompeuses : « recomposition des équilibres », « échiquier stratégique », « nouvelle donne », « bouleversement géopolitique », « dans un contexte de », « montée en puissance » sans faits concrets. Aucune phrase ne doit exister uniquement pour donner de la gravité au sujet.

PRIORITÉ ABSOLUE : LE DÉTAIL QUI FAIT COMPRENDRE LA NEWS. Pour chaque dossier :
- QUOI / OÙ / QUAND / QUI : événement précis, date, lieu exact (pas seulement le pays), acteurs et institutions concernés.
- QU'EST-CE QUI A ÉTÉ OBSERVÉ : chiffres avec unités, évolutions comparées, dimensions d'infrastructures, matériels ou types d'armes, portée/capacités techniques, volumes, géolocalisation et observations satellites lorsque disponibles et corroborés.
- POURQUOI C'EST IMPORTANT CONCRÈTEMENT : traduire un chiffre en capacité opérationnelle (par exemple pour un aérodrome : longueur de piste et quels types d'avions pourraient s'y poser ; distinguer l'atterrissage possible de l'aptitude à soutenir un déploiement prolongé). Pour des sanctions : volumes, routes logistiques, détournements concrets ; pour une offensive : lieux, unités, distances, pertes si documentées.
- QU'EST-CE QUI EST CONFIRMÉ VS ENVISAGÉ : séparer constats, assertions officielles, analyses d'experts, hypothèses. Si la capacité n'est pas vérifiée, ne pas l'affirmer.
- QUOI SURVEILLER : deux ou trois INDICATEURS OBSERVABLES spécifiques (pas « évolution des tensions »).
Les 3 à 5 paragraphes du body suivent cet ordre. Le champ significance doit expliquer en 2 phrases les implications vérifiables ; watch doit nommer des faits mesurables.
Effectue des recherches web ciblées sur les 3 ou 4 sujets retenus, et sur leurs caractéristiques techniques si disponibles. Ne te contente pas des titres ou des extraits ; si les détails sont inaccessibles, indique la lacune au lieu de broder. Un bon dossier doit pouvoir apprendre au lecteur au moins deux faits précis qu'un résumé général omettrait. Préfère moins de dossiers plutôt que d'étirer artificiellement la matière.
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
                "title":a["title"],"url":a["url"],"excerpt":a["excerpt"][:600]}
               for a in candidates]
    response = OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
        tools=[{"type":"web_search","search_context_size":"medium"}],
        text={"format":{"type":"json_schema","name":"geopolitical_digest","strict":True,"schema":DIGEST_SCHEMA}},
        parallel_tool_calls=False,
        max_output_tokens=8600,
        input=[
            {"role":"system","content":EDITORIAL_RULES},
            {"role":"user","content":"Date UTC : "+now.date().isoformat()+"; corpus de "+str(len(compact))+
             " publications des 7 derniers jours :\n"+json.dumps(compact,ensure_ascii=False)}
        ])
    print("Usage:", response.usage)
    if response.status != "completed":
        raise RuntimeError("Draft response incomplete: " + str(response.status))
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
    prompt = """Tu es le fact-checker de la revue Intelligence Feed. Tu dois réviser le BROUILLON géopolitique fourni. Vérifie activement, avec la recherche web, chaque dossier et ses faits MATÉRIELS (dimensions, portée, modèles d'avions ou d'armes, nombre de sites, chiffres et unités). Corrige les contradictions, distingue « utilisable en théorie » de « utilisé effectivement », et supprime les généralités sans contenu. Un paragraphe peut être réécrit pour ajouter une précision vérifiée — ne jamais inventer des chiffres pour remplir l'espace. Vérifie également les principales affirmations factuelles datées : la chronologie, le caractère temporaire ou résolu d'un incident, les dates d'ouverture d'installations militaires, le statut des élections, les personnes, les capacités militaires, et la correspondance avec les articles cités.
Élimine ou nuance toute affirmation non corroborée. N'écris PAS au présent une restriction déjà levée. Ne présente PAS un événement de septembre ou octobre comme une nouveauté de novembre. Attention à la différence entre les preuves accessibles et les hypothèses d'analystes. Les sources du corpus sont des liens, parfois seulement un extrait; ne prétends pas avoir vérifié des détails que tu ne peux pas confirmer.
Retourne uniquement le même objet JSON, conservant la structure et l'essentiel de la profondeur analytique : title, subtitle, lead, at_a_glance, sections (heading, body, significance, watch, source_ids), maps (title, why, source_id), further_reading. Chaque source_id doit appartenir à la liste. N'ajoute pas de fait nouveau sans source appropriée. Corrige toute erreur détectée sans embellir. Remplace les formules vagues par des détails sourcés quand ces données sont disponibles et vérifiées. Si une information technique manque, dis explicitement qu'elle n'est pas connue. Ne fabrique pas de précision."""
    resp = OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
        tools=[{"type":"web_search","search_context_size":"medium"}],
        text={"format":{"type":"json_schema","name":"geopolitical_digest","strict":True,"schema":DIGEST_SCHEMA}},
        parallel_tool_calls=False,
        max_output_tokens=7500,
        input=[
            {"role":"system","content":prompt},
            {"role":"user","content":"Date : "+now.date().isoformat()+"\nSOURCES DISPONIBLES : "+
             json.dumps(source_index,ensure_ascii=False)+
             "\nARTICLE A AUDITER : "+json.dumps(digest,ensure_ascii=False)}
        ])
    print("Fact check usage:",resp.usage)
    if resp.status != "completed":
        raise RuntimeError("Fact-check response incomplete: " + str(resp.status))
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
