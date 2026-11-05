"""Deterministic publication gates, independent of model availability and API cost."""
import re
from collections import defaultdict

MAX_CANDIDATES = 40
MAX_DIGEST_WORDS = 2050
MIN_DIGEST_WORDS = 380
MAX_SECTIONS = 4
MIN_SECTIONS = 2

class RecoverableDigestError(Exception):
    """Expected source/API/editorial problem: keep the last published issue."""

def select_candidates(candidates, limit=MAX_CANDIDATES):
    """Bound input size without losing entire publishers to recency sorting."""
    by_publisher = defaultdict(list)
    for item in candidates:
        by_publisher[item["publisher"]].append(item)
    result = []
    selected = set()
    # At least seven recent publications per available publisher, if present.
    for _, group in sorted(by_publisher.items()):
        for item in group[:7]:
            if len(result) >= limit:
                break
            if item["id"] not in selected:
                result.append(item)
                selected.add(item["id"])
    for item in candidates:
        if len(result) >= limit:
            break
        if item["id"] not in selected:
            result.append(item)
            selected.add(item["id"])
    return sorted(result, key=lambda item: item["date"], reverse=True)

def count_words(value):
    return len(re.findall(r"\b[\wÀ-ÿ]+(?:[-’'][\wÀ-ÿ]+)*\b", value, flags=re.UNICODE))

def inspect_report(report, candidates):
    """Return actionable defects. Never mutate a model response to fabricate citations."""
    errors = []
    if not isinstance(report, dict):
        return ["The response is not a JSON object"]
    allowed = {c["id"] for c in candidates}
    for field in ("title", "subtitle", "lead"):
        value = report.get(field)
        if not isinstance(value, str) or len(value.strip()) < 12:
            errors.append("Missing or short "+field)
    summary = report.get("at_a_glance")
    if not isinstance(summary, list) or not 3 <= len(summary) <= 7 or any(not isinstance(x, str) or len(x.strip()) < 15 for x in summary):
        errors.append("Summary must contain 3–7 meaningful sentences")
    sections = report.get("sections")
    if not isinstance(sections, list) or not MIN_SECTIONS <= len(sections) <= MAX_SECTIONS:
        errors.append("Need between 2 and 4 substantive, sourced dossiers")
        sections = sections if isinstance(sections, list) else []
    for n, section in enumerate(sections):
        if not isinstance(section, dict):
            errors.append(f"Dossier {n+1} not an object")
            continue
        if not isinstance(section.get("heading"), str) or len(section["heading"].strip()) < 12:
            errors.append(f"Dossier {n+1}: missing heading")
        body = section.get("body")
        if not isinstance(body, list) or not 2 <= len(body) <= 6 or any(not isinstance(p,str) or len(p.strip()) < 65 for p in body):
            errors.append(f"Dossier {n+1}: need 2–6 substantive paragraphs")
        references = section.get("source_ids")
        if not isinstance(references, list) or not references or any(type(i) is not int or i not in allowed for i in references):
            errors.append(f"Dossier {n+1}: missing or unverified article identifiers")
        for key in ("significance", "watch"):
            if not isinstance(section.get(key), str) or len(section[key].strip()) < 25:
                errors.append(f"Dossier {n+1}: missing {key} / strategic explanation")
    maps = report.get("maps")
    if not isinstance(maps, list) or len(maps) > 3:
        errors.append("Map source list invalid or exceeds three")
    else:
        for m in maps:
            if not isinstance(m, dict) or type(m.get("source_id")) is not int or m["source_id"] not in allowed:
                errors.append("Map references must identify a verified input article")
    reading = report.get("further_reading")
    if not isinstance(reading, list) or len(reading) > 5 or any(type(i) is not int or i not in allowed for i in reading):
        errors.append("Reading recommendations contain unknown article IDs")
    full_text = " ".join([
        str(report.get("title","")), str(report.get("subtitle","")), str(report.get("lead","")),
        *[x for x in summary or [] if isinstance(x,str)]
    ]+[
        text for section in sections if isinstance(section,dict)
        for text in (section.get("body",[]) if isinstance(section.get("body"),list) else [])
        if isinstance(text,str)
    ]+[
        str(section.get(field,"")) for section in sections if isinstance(section,dict)
        for field in ("significance","watch")
    ])
    words=count_words(full_text)
    if words < MIN_DIGEST_WORDS or words > MAX_DIGEST_WORDS:
        errors.append(f"Length {words} words, target {MIN_DIGEST_WORDS}-{MAX_DIGEST_WORDS}")
    return errors

def assert_report(report,candidates):
    errors=inspect_report(report,candidates)
    if errors:
        raise RecoverableDigestError("; ".join(errors))
    return report

def compact_for_model(candidates):
    """Hard cap input size, preserving metadata and publisher coverage."""
    chosen=select_candidates(candidates)
    return [{"id":c["id"],"publisher":c["publisher"],"date":c["date"][:10],
             "title":c["title"][:160],"url":c["url"],"excerpt":c.get("excerpt","")[:310]}
            for c in chosen]
