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
    "ai producer", "ai producing", "ai lead", "creative strategy",
    "creative lead", "creative director", "associate creative director", "ugc",
    "creative producer",
    # Widened 2026-09-16 per Can's explicit priority shift: speed to a
    # landed remote role beats narrow precision right now. Synced against
    # his own PROJECT-EXIT repo's authoritative target-role list rather than
    # guessing new terms — these are roles he already decided matter.
    "integrated creative", "brand strategist", "brand creative",
    "campaign strategist", "creative innovation", "creative technologist",
]

# Shared title-match regex for the eight approved role families. Search
# queries for LinkedIn/Indeed/Glassdoor/Google Jobs are already narrowed to
# these terms (config.json), but those platforms' own search relevance is
# fuzzy and can surface off-mission titles anyway (e.g. "Growth Marketing
# Manager" showing up for a "Creative Strategy remote" query) — this regex
# is the hard title-level check applied at delivery time to close that gap,
# on top of the soft keyword-weighted fit score.
ROLE_TERMS = re.compile(
    "|".join(
        # "creative strategy" as a literal phrase misses the far more common
        # title noun form "Creative Strategist" — stem the word instead of
        # escaping it literally. Caught 2026-09-16 testing this regex as a
        # hard delivery gate: it would have rejected "Senior Creative
        # Strategist", a real, on-mission title.
        # Allow one word between "creative" and "strateg*" — real titles
        # insert a word here ("Creative Performance Strategist" got wrongly
        # rejected 2026-09-16 while "Performance Creative Strategist" passed,
        # purely by word order). Forward direction only (creative first) —
        # the reverse ("...strategy and creative...") matched unrelated
        # titles like "Growth Strategy and Creative Ops Manager" in testing.
        r"creative(?:\s+\w+)?\s+strateg\w*"
        if t == "creative strategy" else re.escape(t)
        for t in ADJACENT_TERMS
    ),
    re.I,
)

FALSE_NEGATIVE_EXCLUDES = {
    "customer success", "project coordinator", "account director", "account lead",
    "client partner", "brand manager", "campaign manager",
}

# Keep every hourly board scan small. One rotating adjacent family is added per
# hour so coverage grows through the day without hammering public endpoints.
CORE_REMOTE_TERMS = [
    "ai producer remote",
    "ai producing remote",
    "ai lead remote",
    "creative strategy remote",
    "creative lead remote",
    "creative director remote",
    "associate creative director remote",
    "ugc remote",
    "creative producer remote",
    "integrated creative remote",
    "brand strategist remote",
    "brand creative remote",
    "campaign strategist remote",
    "creative innovation remote",
    "creative technologist remote",
]
# Query-diversity variants of the approved roles (not new roles — each
# phrase still contains one of ROLE_TERMS' patterns, so nothing extra gets
# past the hard delivery gate; this just changes what each platform's search
# relevance surfaces per hour). One group active per hourly slot.
ROTATING_REMOTE_TERM_GROUPS = [
    ["senior creative director remote", "global creative lead remote"],
    ["brand creative director remote", "creative strategy lead remote"],
    ["executive creative director remote", "content creative lead remote"],
    ["group creative director remote", "creative producer lead remote"],
]


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
    merged = []
    seen = set()
    for term in list(current) + list(terms):
        value = str(term)
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            merged.append(value)
    config["search_terms"][source] = merged


def _prepare_remote_first(config):
    """Repair known source/config drift and widen discovery without paid APIs."""
    locations = config.setdefault("locations", {})

    # python-jobspy accepts UK / United Kingdom, not the legacy GB alias.
    for source in ("indeed", "google_jobs"):
        for geo in locations.get(source, []):
            if isinstance(geo, dict) and str(geo.get("country", "")).strip().lower() == "gb":
                geo["country"] = "UK"

    # Keep discovery restricted to the configured UK/European locations.

    target = config.setdefault("target_geography", {})
    target["require_remote"] = True
    target["exclude_us"] = True
    target_locations = target.setdefault("locations", [])
    for item in ():
        if item not in target_locations:
            target_locations.append(item)

    terms = config.setdefault("location_filter", {}).setdefault("terms", [])
    for item in ():
        if item not in terms:
            terms.append(item)

    # Repair role families that had previously been accidentally blacklisted.
    keywords = config.setdefault("keywords", {})
    excludes = keywords.setdefault("exclude", [])
    keywords["exclude"] = [x for x in excludes if str(x).casefold() not in FALSE_NEGATIVE_EXCLUDES]
    includes = keywords.setdefault("include", [])
    keywords["include"] = list(dict.fromkeys(includes + ADJACENT_TERMS))

    # Keep the complete intent available when discovery lanes are disabled (and
    # for tests/manual runs). The enabled production path below replaces these
    # with a much smaller rotating set before scraper constants are initialized.
    remote_adjacent = [f"{term} remote" for term in ADJACENT_TERMS]
    for source in ("linkedin", "indeed", "glassdoor", "google_jobs", "ziprecruiter"):
        _append_terms(config, source, remote_adjacent)

    profile = config.setdefault("profile", {})
    profile["subtitle"] = "Remote · UK / Europe · AI Production & Creative Leadership"
    return config


def _bounded_geos(config, slot):
    """Always scan global Remote plus one rotating region instead of every geo."""
    locations = config.setdefault("locations", {})

    indeed = [g for g in locations.get("indeed", []) if isinstance(g, dict)]
    worldwide = next((g for g in indeed if str(g.get("country", "")).casefold() == "worldwide"), None)
    regional = [
        g for g in indeed
        if str(g.get("location", "")).casefold() == "remote"
        and str(g.get("country", "")).casefold() != "worldwide"
    ]
    picked = []
    if worldwide:
        picked.append(worldwide)
    if regional:
        picked.append(regional[slot % len(regional)])
    if picked:
        locations["indeed"] = picked

    linkedin = [g for g in locations.get("linkedin", []) if isinstance(g, dict)]
    global_remote = next((g for g in linkedin if str(g.get("location", "")).casefold() == "remote"), None)
    li_regional = [g for g in linkedin if g is not global_remote]
    picked = []
    if global_remote:
        picked.append(global_remote)
    if li_regional:
        picked.append(li_regional[slot % len(li_regional)])
    if picked:
        locations["linkedin"] = picked


def expand_config(config, jobs=(), slot=None):
    """Repair remote discovery and rotate bounded query/geo lanes hourly."""
    config = _prepare_remote_first(config)
    slot = int(datetime.now(timezone.utc).timestamp() // 3600) if slot is None else slot
    settings = config.get("discovery_lanes", {})
    if not settings.get("enabled"):
        return config

    seeds = [
        j for j in jobs
        if target_location(j.get("location", ""))
        and re.search(r"creative|brand strateg|campaign strateg|concept|innovation|technologist|ai", str(j.get("title", "")), re.I)
    ]
    text = " ".join(str(j.get("description", "")) for j in seeds).lower()
    phrases = settings.get("description_phrases", [])
    evidenced = [
        p for p in phrases
        if p.lower().removesuffix(" remote").removesuffix(" creative").removesuffix(" strategist") in text
    ]
    # The focused mode deliberately adds no inferred/company expansion.
    extra = []

    # Cap the active query set. This replaces the large cumulative lists created
    # above, preventing hundreds of JobSpy/LinkedIn calls in a single hour.
    rotating = ROTATING_REMOTE_TERM_GROUPS[slot % len(ROTATING_REMOTE_TERM_GROUPS)]
    active_terms = list(dict.fromkeys(CORE_REMOTE_TERMS + rotating + extra))
    for source in ("linkedin", "indeed", "glassdoor", "google_jobs", "ziprecruiter"):
        config.setdefault("search_terms", {})[source] = active_terms.copy()

    _bounded_geos(config, slot)

    import query_metrics
    query_metrics.EXPERIMENTS.update(extra)

    # Explicit Google queries otherwise bypass search_terms entirely. Keep only
    # a bounded rotating set instead of the old city × title matrix.
    queries = config.setdefault("google_jobs", {}).setdefault("queries", [])
    config["google_jobs"]["queries"] = [
        f"{term} jobs" for term in active_terms[:10]
    ]

    print("Discovery lanes:", {
        "extra_queries": extra,
        "seed_count": len(seeds),
        "description_evidence": evidenced,
        "slot": slot,
        "mode": "remote-first-bounded",
        "active_terms": len(active_terms),
        "linkedin_geos": len(config.get("locations", {}).get("linkedin", [])),
        "indeed_geos": len(config.get("locations", {}).get("indeed", [])),
    })
    return config
