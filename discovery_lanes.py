"""Bounded, free query expansion. No model calls or inferred work authorization."""
import re
from datetime import datetime, timezone

ALIASES = r"\b(london|amsterdam|germany|deutschland|hungary|magyarország|portugal|spain|españa|berlin|munich|münchen|hamburg|frankfurt|cologne|köln|düsseldorf|stuttgart|budapest|lisbon|lisboa|porto|madrid|barcelona|valencia|sevilla|seville|malaga|málaga)\b"

def target_location(location):
    text = str(location).lower()
    return bool(re.search(ALIASES, text)) and not re.search(r"\b(united states|usa|us|california|new york)\b", text)

def expand_config(config, jobs=(), slot=None):
    """Keep core terms; rotate one query per experimental lane per run."""
    slot = int(datetime.now(timezone.utc).timestamp() // 3600) if slot is None else slot
    settings = config.get("discovery_lanes", {})
    if not settings.get("enabled"):
        return config
    seeds = [j for j in jobs if target_location(j.get("location", ""))
             and re.search(r"creative|brand strateg|campaign strateg", str(j.get("title", "")), re.I)]
    text = " ".join(str(j.get("description", "")) for j in seeds).lower()
    phrases = settings.get("description_phrases", [])
    evidenced = [p for p in phrases if p.lower().removesuffix(" remote").removesuffix(" creative").removesuffix(" strategist") in text]
    lanes = [evidenced or phrases, settings.get("contracts", []), settings.get("local_titles", [])]
    companies = sorted({str(j.get("company", "")).strip() for j in seeds if j.get("company")})
    lanes.append([c + " creative remote" for c in companies[:30]])
    extra = [lane[slot % len(lane)] for lane in lanes if lane]
    for source in ("linkedin", "indeed", "glassdoor", "google_jobs"):
        terms = config.setdefault("search_terms", {}).get(source, [])
        config["search_terms"][source] = list(dict.fromkeys(terms + extra))
    # Explicit queries otherwise bypass Google search_terms entirely.
    queries = config.setdefault("google_jobs", {}).setdefault("queries", [])
    geos = config.get("target_geography", {}).get("locations", [])
    if geos:
        queries.extend(q + " jobs " + geos[slot % len(geos)] for q in extra)
    print("Discovery lanes:", {"extra_queries": extra, "seed_count": len(seeds),
                               "description_evidence": evidenced, "slot": slot})
    return config
