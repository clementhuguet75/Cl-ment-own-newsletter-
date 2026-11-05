#!/usr/bin/env python3
"""Research many source items and publish ONE substantial weekly geopolitical digest."""
import json
import os
import re
from datetime import datetime, timezone
from openai import OpenAI, OpenAIError
from sources import collect
from magazine import publish
from guardrails import (
    RecoverableDigestError, inspect_report, assert_report,
    compact_for_model, select_candidates,
)

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

# Publication controls: at most one research + one fact check + two
# structured attempts for each editorial stage (API retries are SDK bounded).
MAX_STRUCTURED_ATTEMPTS = 2
DRAFT_WORD_TARGET = 1300

def web_research(candidates, now):
    """Gather precise OSINT research in short notes; writing is a separate call."""
    prompt = """Réalise les recherches documentaires pour un digest géopolitique FRANÇAIS.
Choisis TROIS sujets importants parmi les publications sourcées. Recherche sur le web et recoupe leurs faits précis, détails militaires/techniques, lieux, dates, distances, matériel et effectifs quand documentés. Fournis des notes FACTUELLES, pas un article. Pour chaque sujet : 5 à 8 faits et leurs références [id], une comparaison avec la situation antérieure, le mécanisme stratégique micro → macro, les limites de l'interprétation et 2 indicateurs observables. Précise ce qui n'est pas vérifié. N'attribue jamais une déclaration à une source qui ne la soutient pas. Max. 1 400 mots de notes; priorité à la précision, pas à la rhétorique."""
    response = OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL","gpt-4.1"),
        tools=[{"type":"web_search","search_context_size":"medium"}],
        max_output_tokens=4200,
        input=[{"role":"system","content":prompt},
               {"role":"user","content":"Date UTC : "+now.date().isoformat()+"\n"+
                json.dumps(compact_for_model(candidates),ensure_ascii=False)}])
    print("Research usage:", response.usage)
    notes=(response.output_text or "").strip()
    if len(notes)<350:
        raise RecoverableDigestError("Insufficient grounded research; not publishing")
    if response.status!="completed":
        # Incomplete notes may omit the source context needed for a safe digest.
        raise RecoverableDigestError("Web research was incomplete; previous issue retained")
    return notes[:15000]

def structured_digest(instructions, user_text, candidates, stage):
    """JSON schema + deterministic semantic validation + ONE bounded repair attempt."""
    prompt=user_text
    last_error="none"
    for attempt in range(MAX_STRUCTURED_ATTEMPTS):
        # 6200 is sufficient for a 1000-1500 word JSON digest; 7400 on repair.
        limit=6200 if attempt==0 else 7400
        response=OpenAI().responses.create(
            model=os.getenv("OPENAI_MODEL","gpt-4.1"),
            text={"format":{"type":"json_schema","name":"geopolitical_digest",
                            "strict":True,"schema":DIGEST_SCHEMA}},
            max_output_tokens=limit,
            input=[{"role":"system","content":instructions},
                   {"role":"user","content":prompt}])
        print(stage,"attempt",attempt+1,"usage:",response.usage)
        if response.status!="completed":
            last_error="Model response incomplete (output length limit)"
            prompt=(user_text+"\nRETRY: The first attempt ran out of tokens. "
                    "Return ONLY 2-3 dossiers, 2 substantial paragraphs per dossier, "
                    "750-1000 words TOTAL, complete JSON. Never leave an unfinished object.")
            continue
        try:
            article=json.loads(response.output_text)
        except (json.JSONDecodeError, TypeError) as exc:
            last_error="Malformed JSON: "+str(exc)[:100]
            prompt=(user_text+"\nRETRY: Output valid, complete JSON only. "
                    "Maximum 1000 words, 2 dossiers and 2 paragraphs per dossier.")
            continue
        defects=inspect_report(article,candidates)
        if not defects:
            return article
        last_error="; ".join(defects)[:700]
        print("::warning::",stage,"output rejected for quality:",last_error)
        prompt=(user_text[:18000]+"\nCORRECT THESE DEFECTS: "+last_error+
                "\nExisting draft (repair, do not invent citations): "+
                json.dumps(article,ensure_ascii=False)[:12000]+
                "\nReturn a full JSON document, 2-3 dossiers, >= 400 and <= 1600 words. "
                "Keep IDs only from the source index.")
    raise RecoverableDigestError(stage+" not publishable after 2 attempts: "+last_error)

def make_digest(candidates, now):
    selected=select_candidates(candidates)
    notes=web_research(selected,now)
    text=("Date: "+now.date().isoformat()+
          "\nDOCUMENTED RESEARCH NOTES (NO UNSOURCED ASSERTIONS):\n"+notes+
          "\nVALID ARTICLE IDs:\n"+json.dumps(compact_for_model(selected),ensure_ascii=False)+
          "\nCompose 3 dossiers, 2-4 substantive paragraphs each, around "+
          str(DRAFT_WORD_TARGET)+" words TOTAL. Explain both precise technical facts "
          "and regional micro-to-macro strategic consequences and limitations. "
          "Every dossier needs a valid source ID. Max 5 summary sentences, 3 maps, 3 further readings. "
          "Return one complete JSON object.")
    draft=structured_digest(EDITORIAL_RULES,text,selected,"draft")
    return draft,notes,selected

def audit_digest(digest,candidates,now,research_notes):
    """Fact check critical assertions; never quietly restore unverified copy."""
    claims=json.dumps(digest,ensure_ascii=False)
    check=OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL","gpt-4.1"),
        tools=[{"type":"web_search","search_context_size":"medium"}],
        max_output_tokens=2700,
        input=[
            {"role":"system","content":"""Vérificateur factuel géopolitique : recoupe les affirmations vérifiables de cet article (dates, lieux, dimension d'une piste, appareils, armes, diplomatie, élections, trêves). Compare à des sources contemporaines via web_search. Distingue faits observés / déclarations / analyses / hypothèses ; signale événements déjà terminés, fausses chronologies, mauvaises unités et citations inadéquates. Réponds uniquement en notes concises de correction, pas en article ni JSON. Si aucune erreur, explique les vérifications les plus importantes. Maximum 700 mots."""},
            {"role":"user","content":"Date "+now.date().isoformat()+"\nARTICLE À AUDITER:\n"+claims}
        ])
    print("Fact check usage:",check.usage)
    findings=(check.output_text or "").strip()
    if check.status!="completed" or len(findings)<100:
        raise RecoverableDigestError("Fact checking incomplete; previous edition retained")
    instructions="""Tu es le réviseur final d'un journal géopolitique personnel. Applique seulement les corrections étayées par l'audit web. Élimine les erreurs factuelles et les inférences non démontrées; ne les réintroduis pas. Conserve 2 à 4 dossiers substantiels, 2-4 paragraphes par dossier, 850-1500 mots. Toute section doit avoir au moins un source_id DÉJÀ PRÉSENT dans le brouillon pour le sujet correspondant, sauf nouveau sujet vérifié avec un autre id authentique. Si l'audit invalide un dossier, supprime-le et approfondis uniquement les dossiers restants. Préserve les faits micro et le vrai mécanisme micro → macro, avec limites et contre-arguments. Donne toutes les références sous forme d'IDs du corpus uniquement. Retourne exclusivement le JSON complet conforme au schéma, pas de Markdown."""
    original_index=json.dumps(compact_for_model(candidates),ensure_ascii=False)
    revisions=("DATE "+now.date().isoformat()+
        "\nSOURCES AUTORISÉES:\n"+original_index+
        "\nCONSTAT DE L'AUDIT:\n"+findings+
        "\nNOTES D'ENQUÊTE:\n"+research_notes[:11000]+
        "\nBROUILLON À CORRIGER:\n"+claims)
    result=structured_digest(instructions,revisions,candidates,"fact-checked revision")
    assert_report(result,candidates)
    return result

def _github_result(published, message):
    """Explicit output lets Actions SKIP deploy on recoverable editorial errors."""
    if not published:
        safe=message.replace("\n"," ")[:500]
        print("::warning::Digest NOT published; previous issue untouched. "+safe)
    else:
        safe=message
        print("Digest published:",safe)
    output=os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output,"a",encoding="utf-8") as f:
            f.write("published="+("true" if published else "false")+"\n")
    summary=os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary,"a",encoding="utf-8") as f:
            f.write("### Intelligence Feed\n"+
                    ("**New edition ready.** " if published else "**No publication (previous edition kept).** ")+
                    message.replace("\n"," ")[:700]+"\n")

def main():
    now=datetime.now(timezone.utc)
    try:
        try:
            candidates=collect(now)
        except RuntimeError as exc:
            if "Insufficient recent articles" in str(exc):
                raise RecoverableDigestError(str(exc)) from exc
            raise
        draft,research_notes,selected=make_digest(candidates,now)
        checked=audit_digest(draft,selected,now,research_notes)
        assert_report(checked,selected)
    except (RecoverableDigestError,OpenAIError) as exc:
        _github_result(False,str(exc))
        return
    # Only the validated final article can reach the publisher.
    # A disk / git / deployment failure remains a real workflow error.
    publish(checked,candidates,now)
    _github_result(True,now.date().isoformat())

if __name__=="__main__":
    main()
