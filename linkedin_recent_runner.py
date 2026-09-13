"""Fast hourly LinkedIn runner with broad-but-bounded title recall.

Deep pagination stays available for backfills. The hourly watcher takes only the
freshest page per rotating remote-first term/geo, then lets downstream scoring
and delivery filters decide precision.
"""
import re
import scrape_jobs as jobs

_original_search = jobs._linkedin_search
_original_relevant = jobs.linkedin_role_is_relevant

# Adjacent families the candidate explicitly accepts. Keep this broader than the
# final delivery gate: source discovery should maximize recall, while scoring,
# remote/language checks and fit thresholds provide precision later.
_ADJACENT_TITLE_RE = re.compile(
    r"\b(?:brand|growth|performance|digital|integrated)\s+marketing\b"
    r"|\bmarketing\s+(?:strategy|strategist|operations|ops|lead|director)\b"
    r"|\b(?:project|program)\s+(?:manager|lead|director)\b"
    r"|\b(?:client|customer)\s+(?:success|services|delivery|operations)\b"
    r"|\baccount\s+(?:manager|director|lead)\b"
    r"|\b(?:implementation|onboarding)\s+(?:manager|lead|specialist|consultant)\b"
    r"|\b(?:partnership|partnerships)\s+(?:manager|lead|director)\b"
    r"|\bai\s+(?:strategist|strategy|workflow|workflows|operations|automation)\b"
    r"|\b(?:workflow|automation)\s+(?:manager|lead|strategist|consultant)\b",
    re.IGNORECASE,
)

# Obvious non-target families should never be rescued by the broad adjacent
# matcher. Existing config exclusions are also respected below.
_HARD_REJECT_RE = re.compile(
    r"\b(?:software|frontend|front-end|backend|back-end|full[- ]?stack|data scientist|"
    r"engineer|engineering|developer|product designer|ux|ui|graphic designer|"
    r"video editor|videographer|medical|clinical|scientist)\b",
    re.IGNORECASE,
)


def _hourly_relevant(title, company=""):
    if _original_relevant(title, company):
        return True
    if not title or jobs.EXCLUDED_SENIORITY_RE.search(title) or _HARD_REJECT_RE.search(title):
        return False
    return bool(_ADJACENT_TITLE_RE.search(title))


def _hourly_search(terms, lookback_seconds, geos=None, max_results=500):
    # One LinkedIn guest-result page (10 cards) per active term/geo. Discovery
    # lanes already rotate terms and regions hourly, while always retaining the
    # global Remote lane.
    return _original_search(
        terms,
        lookback_seconds,
        geos=geos,
        max_results=min(int(max_results or 10), 10),
    )


jobs.linkedin_role_is_relevant = _hourly_relevant
jobs._linkedin_search = _hourly_search

result = jobs.scrape_linkedin_recent()
before = len(result)
result = [j for j in result if jobs.is_target_location(j.get("location", ""))]
print(f"📍 Location filter: {before} → {len(result)} roles")
jobs.save_linkedin_results(result)
