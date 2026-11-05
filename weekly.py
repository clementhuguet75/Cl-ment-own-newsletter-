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

LONGUEUR CONTRÔLÉE : exactement 3 ou 4 dossiers, trois paragraphes de 90 à 130 mots par dossier (exceptionnellement quatre si les faits le justifient). Maximum 1 900 mots pour l'ensemble de l'article, en excluant le JSON. Chaque paragraphe doit contenir des informations vérifiables : aucun remplissage. Le JSON doit être compact et complet. N'allonge jamais artificiellement une section.

PRIORITÉ ABSOLUE : LE DÉTAIL QUI FAIT COMPRENDRE LA NEWS. Pour chaque dossier :
- QUOI / OÙ / QUAND / QUI : événement précis, date, lieu exact (pas seulement le pays), acteurs et institutions concernés.
- QU'EST-CE QUI A ÉTÉ OBSERVÉ : chiffres avec unités, évolutions comparées, dimensions d'infrastructures, matériels ou types d'armes, portée/capacités techniques, volumes, géolocalisation et observations satellites lorsque disponibles et corroborés.
- POURQUOI C'EST IMPORTANT CONCRÈTEMENT : traduire un chiffre en capacité opérationnelle (par exemple pour un aérodrome : longueur de piste et quels types d'avions pourraient s'y poser ; distinguer l'atterrissage possible de l'aptitude à soutenir un déploiement prolongé). Pour des sanctions : volumes, routes logistiques, détournements concrets ; pour une offensive : lieux, unités, distances, pertes si documentées.
- QU'EST-CE QUI EST CONFIRMÉ VS ENVISAGÉ : séparer constats, assertions officielles, analyses d'experts, hypothèses. Si la capacité n'est pas vérifiée, ne pas l'affirmer.
- QUOI SURVEILLER : deux ou trois INDICATEURS OBSERVABLES spécifiques (pas « évolution des tensions »).
OBLIGATION EDITORIALE : FAIRE LE PONT MICRO → MACRO (« SO WHAT ? »).
Pour CHAQUE dossier, après les détails matériels, répondre explicitement et concrètement :
1) CONTEXTE PREEXISTANT : quel projet, conflit, réseau, tendance ou objectif stratégique existait AVANT cet événement ? Où se situe l'événement dans cette carte (voisins, routes, alliances, autres bases, capacités existantes) ? Utilise deux faits historiques/géographiques vérifiables pour ancrer cette lecture.
2) MECANISME DE CAUSALITE : quel comportement, quelle capacité, quel levier de pression ou quelle option l'événement rend-il possible, pour QUI et contre QUI ? Explique le mécanisme, pas uniquement « cela renforce l'influence ».
3) CONTREFACTUEL ET IMPORTANCE RELATIVE : qu'est-ce qui change réellement par rapport à la situation AVANT l'événement ? Est-ce une rupture, une accélération d'une dynamique ancienne ou un petit signal ? Distingue capacité technique théorique et déploiement réel. Donne au lecteur la conclusion « so what » en 2-3 phrases sans exagérer.
4) REACTIONS ET PERSPECTIVES : identifie les acteurs concernés et explique pourquoi ils pourraient s'en inquiéter, ou au contraire relativiser le fait. Présente un désaccord analytique s'il est étayé.
Ne pas fabriquer une grande histoire stratégique à partir d'une anecdote. Si l'incidence stratégique démontrable est faible, DIS-LE franchement. Une analyse doit relier les détails micro au jeu régional ou mondial, sans jargon.
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

def compact_candidates(candidates):
    return [{"id":a["id"],"publisher":a["publisher"],"date":a["date"][:10],
             "title":a["title"],"url":a["url"],"excerpt":a["excerpt"][:600]} for a in candidates]

def web_research(candidates, now):
    """Search the important facts BEFORE asking for long structured writing."""
    prompt = """Réalise une recherche documentaire OSINT pour un digest géopolitique du jour.
Lis la liste de publications récentes, hiérarchise 3 sujets importants et concrets, puis effectue des recherches web ciblées pour recouper les faits et détails techniques. Réponds EN NOTES FACTUELLES, pas en article, pas en JSON.
Pour chaque sujet : date et lieu exacts, 5 à 8 faits sourcés (avec les id des articles de la liste), données physiques/quantitatives vérifiées (longueurs de pistes, types d'avion, lieux, distances, capacités, effectifs, etc.), portée opérationnelle et limites. Indique également le CONTEXTE MACRO PRÉEXISTANT (stratégie nationale, autres infrastructures comparables, voisins, rivalités), la chaîne causale « so what », et le contre-argument qui relativise l'importance de la news. Aucune invention. Ce qui n'est pas confirmé doit être marqué non confirmé. Sépare les nouveautés des faits anciens utilisés comme contexte.
Ne mentionne que les numéros d'articles de la liste fournie. Si une information décisive manque, dis-le clairement. Ne produis PAS de phrases creuses. Maximum 1 800 mots de notes."""
    response = OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL","gpt-4.1"),
        tools=[{"type":"web_search","search_context_size":"medium"}],
        max_output_tokens=4800,
        input=[{"role":"system","content":prompt},
               {"role":"user","content":"Date UTC "+now.date().isoformat()+"; candidats : "+
                json.dumps(compact_candidates(candidates),ensure_ascii=False)}])
    print("Research usage:", response.usage)
    notes=(response.output_text or "").strip()
    if len(notes)<300:
        raise RuntimeError("Not enough grounded research notes for publication")
    return notes[:18000]

def structured_digest(instructions, user_text, output_limit=8000):
    """Constrained output without web tools, avoiding web+schema token exhaustion."""
    response = OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL","gpt-4.1"),
        text={"format":{"type":"json_schema","name":"geopolitical_digest","strict":True,"schema":DIGEST_SCHEMA}},
        max_output_tokens=output_limit,
        input=[{"role":"system","content":instructions},{"role":"user","content":user_text}])
    print("Structured output usage:", response.usage)
    if response.status!="completed":
        raise RuntimeError("Structured output was incomplete; previous issue preserved")
    return json.loads(response.output_text)

def make_digest(candidates, now):
    notes=web_research(candidates,now)
    user_text=("Date : "+now.date().isoformat()+
        "\nNOTES D'ENQUÊTE WEB, À UTILISER COMME SEUL FONDEMENT DES FAITS :\n"+notes+
        "\nINDEX DES SOURCES ET ID AUTORISÉS :\n"+json.dumps(compact_candidates(candidates),ensure_ascii=False)+
        "\nCompose exactement 3 dossiers, 3 paragraphes factuels de 90-120 mots chacun, un chapô, cinq phrases d'essentiel, 1-3 cartes SOURCÉES et 3 lectures. Maximum 1600 mots. Ne force aucun détail que les recherches n'étayent pas. Évite les généralités. Sortie JSON valide et COMPLÈTE.")
    draft=structured_digest(EDITORIAL_RULES,user_text)
    return draft,notes

def audit_digest(digest, candidates, now, research_notes):
    """Independently check claims, then revise in bounded, tool-free JSON."""
    index=[{"id":x["id"],"title":x["title"],"publisher":x["publisher"],
            "date":x["date"][:10],"url":x["url"]} for x in candidates]
    claims=json.dumps(digest,ensure_ascii=False)
    check=OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL","gpt-4.1"),
        tools=[{"type":"web_search","search_context_size":"medium"}],
        max_output_tokens=2500,
        input=[
            {"role":"system","content":"""Vérificateur factuel géopolitique. En utilisant la recherche web, contrôle les affirmations matérielles et temporelles de l'article : dates, élections, acteurs, longueur des pistes, types d'avions, usage réel vs possibilité théorique, chiffres et statut résolu ou actif. Réponds en NOTES DE CORRECTION COURTES, pas en JSON ni article. Si tu ne peux pas prouver un détail, indique précisément le passage à nuancer ou supprimer. N'ajoute pas d'événements non pertinents. Maximum 850 mots."""},
            {"role":"user","content":"Date "+now.date().isoformat()+"\nBROUILLON : "+claims}
        ])
    print("Fact check web usage:",check.usage)
    findings=(check.output_text or "").strip()
    if len(findings)<80:
        raise RuntimeError("Fact checking yielded insufficient evidence; previous edition preserved")
    instructions="""Tu es le réviseur final d'un digest géopolitique français. Corrige le brouillon uniquement selon les constats d'audit vérifiés. Garde la profondeur technique et la structure JSON. Enlève toute information douteuse, remplace les adjectifs vagues par faits réellement justifiés, et distingue toujours passé et présent. Maximum 1600 mots pour l'article total. Pour chaque dossier, vérifie également si la conclusion stratégique est réellement déduite des faits et de la situation régionale et si elle évite de transformer une capacité hypothétique en fait acquis. Essaie de conserver les trois dossiers du brouillon lorsqu'ils sont justifiés, mais préfère supprimer entièrement un sujet si ses faits essentiels sont démentis. Tu peux raccourcir, pas inventer. Toutes les sources sont des id entiers existants. OBLIGATION ABSOLUE : chaque section conserve au moins un source_id du brouillon correspondant, tant que l'affirmation est conservée. Ne retourne JAMAIS une liste source_ids vide. Si tu supprimes un sujet non étayé, réécris le dossier à partir d'un sujet factuellement documenté et attribue des sources réelles de l'index. N'ajoute ni publication ni précision absente des notes d'enquête et de vérification."""
    final=structured_digest(instructions, "INDEX DES ARTICLES : "+json.dumps(index,ensure_ascii=False)+
              "\nNOTES INITIALES : "+research_notes[:12000]+
              "\nNOTES D'AUDIT WEB : "+findings+
              "\nBROUILLON À CORRIGER : "+claims)
    allowed={x["id"] for x in candidates}
    sections=final.get("sections",[])
    if not sections or len(sections)>5:
        raise RuntimeError("No defensible audited sections")
    print("Accepted",len(sections),"fact-checked and sourced dossier(s)")
    original_sections=digest.get("sections",[])
    for position, sec in enumerate(sections):
        valid_ids=[i for i in sec.get("source_ids",[]) if type(i) is int and i in allowed]
        if not valid_ids:
            # Never publish an unsupported revised section. Restore the whole original
            # section, including its own relevant citation IDs, not bare links.
            original=original_sections[position] if position < len(original_sections) else {}
            original_ids=[i for i in original.get("source_ids",[]) if type(i) is int and i in allowed]
            if not original_ids or not original.get("body"):
                raise RuntimeError("Neither revision nor original has supported sources")
            print("Reverting unsupported revision in section",position+1)
            sections[position]=original
        else:
            sec["source_ids"]=valid_ids
            if not sec.get("body"):
                raise RuntimeError("Empty section after audit")
    final["maps"]=[m for m in final.get("maps",[]) if type(m.get("source_id")) is int and m["source_id"] in allowed]
    final["further_reading"]=[i for i in final.get("further_reading",[]) if type(i) is int and i in allowed]
    return final



def main():
    now = datetime.now(timezone.utc)
    candidates = collect(now)
    report, research_notes = make_digest(candidates,now)
    checked = audit_digest(report,candidates,now,research_notes)
    publish(checked,candidates,now)

if __name__ == "__main__":
    main()
