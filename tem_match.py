"""TEM-like semantic scoring for Can's preferred remote creative/AI roles."""
import json
import re


def _text(job):
    return " ".join(str(job.get(k, "")) for k in ("title", "company", "location", "description", "work_arrangement"))


def _has(text, *terms):
    return any(re.search(term, text, re.I) for term in terms)


def tem_score(job):
    text = _text(job)
    title = str(job.get("title", ""))
    reasons = []
    score = 0

    # Hard eligibility: do not reward jobs that are clearly incompatible.
    if _has(text, r"\b(on[- ]?site only|onsite only|hybrid only|not remote|no remote)\b"):
        return 0, ["not remote"]
    if _has(text, r"\b(remote[- /]?(?:us|usa|u\.s\.) only|united states only)\b"):
        return 0, ["US-only"]
    if _has(text, r"\b(?:fluent|native|c1|c2)\s+(?:german|dutch)\b", r"\b(?:german|dutch)\s+(?:required|c1|c2)\b"):
        return 0, ["language requirement"]

    if _has(text, r"\b(ai[- ]first|ai[- ]native|ai[- ]driven|generative ai|creative ai|ai tools?|ai workflows?)\b"):
        score += 24; reasons.append("AI-first creative workflow")
    if _has(title, r"brand.*creative", r"creative.*lead", r"creative director", r"head of creative", r"head of brand", r"brand design lead", r"creative strategy lead"):
        score += 20; reasons.append("brand/creative leadership")
    elif _has(title, r"creative strateg", r"brand strateg", r"creative technolog", r"creative innovation", r"ai creative"):
        score += 14; reasons.append("target role family")
    if _has(text, r"concept(?:ing|s)?", r"ideation", r"hands[- ]on", r"creative craft", r"iteration"):
        score += 16; reasons.append("hands-on concepting")
    if _has(text, r"startup", r"scale[- ]?up", r"high[- ]growth", r"fast[- ]moving"):
        score += 12; reasons.append("startup/scale-up")
    if _has(text, r"remote[- ]first", r"fully remote", r"distributed", r"\bremote\b"):
        score += 12; reasons.append("remote")
    if _has(text, r"product.*growth", r"growth.*product", r"cross[- ]functional", r"product adoption", r"business outcomes"):
        score += 8; reasons.append("Product/Growth collaboration")
    if _has(text, r"creative system", r"brand identity", r"campaign storytelling", r"multi[- ]channel campaign", r"creative standards"):
        score += 8; reasons.append("creative systems/campaigns")

    return min(score, 100), reasons


def enrich(job):
    score, reasons = tem_score(job)
    job = dict(job)
    job["tem_score"] = score
    job["tem_match"] = "gold" if score >= 72 else "strong" if score >= 58 else "adjacent"
    job["tem_reasons"] = reasons
    return job
