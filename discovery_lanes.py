"""Bounded, free remote-first query expansion. No model calls or inferred work authorization."""
import re
from datetime import datetime, timezone

REMOTE = re.compile(r"\b(remote|work from home|work-from-home|distributed|anywhere|worldwide|global|emea|europe)\b", re.I)
LOCAL_ALIASES = re.compile(
    r"\b(london|amsterdam|germany|deutschland|hungary|magyarország|portugal|spain|españa|"
    r"berlin|munich|münchen|hamburg|frankfurt|cologne|köln|düsseldorf|stuttgart|budapest|"
    r"lisbon|lisboa|porto|madrid|barcelona|valencia|sevilla|seville|malaga|málaga)\b",
    re.I,
)
US_ONLY = re.compile(
    r"\b(?:remote\s*[-,/ ]*\s*(?:us|usa|u\.s\.|united states)\s*only|"
    r"(?:us|usa|u\.s\.|united states)\s*[-,/ ]*\s*(?:only|residents? only|candidates? only))\b",
    re.I,
)

ADJACENT_TERMS = [
    "performance marketing", "growth marketing", "marketing operations",
    "project manager", "program manager", "project lead", "program lead",
    "customer success manager", "client success", "account manager",
    "account director", "account lead", "client partner", "client services",
    "implementation manager", "implementation specialist", "onboarding manager",
    "solutions consultant", "ai workflow", "ai operations", "automation",
    "brand manager", "campaign manager",
]

FALSE_NEGATIVE_EXCLUDES = {
    "customer success", "project coordinator", "account director", "account lead",
    "client partner", "brand manager", "campaign manager",
}


def target_location(location):
    """Remote-first seed selection; reject only an explicit US-only label."""
    text = str(location or "")
    return bool(REMOTE.search(text) or LOCAL_ALIASES.search(text)) and not US_ONLY.search(text)


def _append_geo(config, source, geo):
    locations = config.setdefault("locations", {}).setdefault(source, [])
    signature = tuple(sorted((str(k), str(v).lower()) for k, v in geo.items()))
    existing = {
        tuple(sorted((str(k), str(v).lower()) for k, v in item.items()))
        for item in locations if isinstance(item, dict)
    }
    if signature not in existing:
        locations.append(geo)


def _append_terms(config, source, terms):
    current = config.setdefault("search_terms", {}).setdefault(source, [])
    config["search_terms"][source] = list(dict.fromkeys(current + list(terms)))


def _prepare_remote_first(config):
    """Repair known source/config drift and widen discovery without paid APIs."""
    locations = config.setdefault("locations", {})

    # python-jobspy accepts UK / United Kingdom, not the legacy GB alias.
    for source in ("indeed", "google_jobs"):
        for geo in locations.get(source, []):
            if isinstance(geo, dict) and str(geo.get("country", "")).strip().lower() == "gb":
                geo["country"] = "UK"

    # JobSpy needs a supported country even when the location itself is Remote.
    for country in ("UK", "Netherlands", "Germany", "Hungary", "Portugal", "Spain"):
        _append_geo(config, "indeed", {"location": "Remote", "country": country})

    _append_geo(config, "linkedin", {"location": "Remote", "name": "Remote", "geoId": ""})
    _append_geo(config, "ziprecruiter", {"location": "Remote", "country": "USA"})

    target = config.setdefault("target_geography", {})
    target["require_remote"] = True
    target["exclude_us"] = False
    target_locations = target.setdefault("locations", [])
    for item in ("Remote", "Worldwide", "Global", "EMEA", "Europe"):
        if item not in target_locations:
            target_locations.append(item)

    terms = config.setdefault("location_filter", {}).setdefault("terms", [])
    for item in ("remote", "worldwide", "global", "anywhere", "emea", "europe"):
        if item not in terms:
            terms.append(item)

    # Earlier tuning accidentally blacklisted several career-adjacent families
    # the user explicitly wants. Repair that at the single config chokepoint so
    # every source sees the same strategy even before config.json is cleaned up.
    keywords = config.setdefault("keywords", {})
    excludes = keywords.setdefault("exclude", [])
    keywords["exclude"] = [x for x in excludes if str(x).casefold() not in FALSE_NEGATIVE_EXCLUDES]
    includes = keywords.setdefault("include", [])
    keywords["include"] = list(dict.fromkeys(includes + ADJACENT_TERMS))

    remote_adjacent = [f"{term} remote" for term in ADJACENT_TERMS]
    for source in ("linkedin", "indeed", "glassdoor", "google_jobs", "hiring_cafe", "ziprecruiter"):
        _append_terms(config, source, remote_adjacent)

    profile = config.setdefault("profile", {})
    profile["subtitle"] = "Remote-first · Worldwide / EMEA · creative + adjacent commercial roles"
    return config


def expand_config(config, jobs=(), slot=None):
    """Repair remote discovery, keep core terms, rotate one query per experimental lane."""
    config = _prepare_remote_first(config)
    slot = int(datetime.now(timezone.utc).timestamp() // 3600) if slot is None else slot
    settings = config.get("discovery_lanes", {})
    if not settings.get("enabled"):
        return config

    seeds = [
        j for j in jobs
        if target_location(j.get("location", ""))
        and re.search(r"creative|brand strateg|campaign strateg|marketing|project|program|client|account|implementation", str(j.get("title", "")), re.I)
    ]
    text = " ".join(str(j.get("description", "")) for j in seeds).lower()
    phrases = settings.get("description_phrases", [])
    evidenced = [
        p for p in phrases
        if p.lower().removesuffix(" remote").removesuffix(" creative").removesuffix(" strategist") in text
    ]
    lanes = [evidenced or phrases, settings.get("contracts", []), settings.get("local_titles", [])]
    companies = sorted({str(j.get("company", "")).strip() for j in seeds if j.get("company")})
    lanes.append([c + " remote" for c in companies[:30]])
    extra = [lane[slot % len(lane)] for lane in lanes if lane]

    import query_metrics
    query_metrics.EXPERIMENTS.update(extra)
    for source in ("linkedin", "indeed", "glassdoor", "google_jobs"):
        _append_terms(config, source, extra)

    # Explicit Google queries otherwise bypass search_terms entirely.
    queries = config.setdefault("google_jobs", {}).setdefault("queries", [])
    geos = config.get("target_geography", {}).get("locations", [])
    if geos:
        queries.extend(q + " jobs " + geos[slot % len(geos)] for q in extra)

    print("Discovery lanes:", {
        "extra_queries": extra,
        "seed_count": len(seeds),
        "description_evidence": evidenced,
        "slot": slot,
        "mode": "remote-first",
    })
    return config
