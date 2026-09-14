"""Free, key-less job boards: Remote OK, Remotive, We Work Remotely.

All three are genuinely free (no signup, no API key) and remote-native, so
there is no IP-block risk the way there is with Glassdoor/Google Jobs
scraping. Output is normalized into the same job schema the rest of
JobFinder uses (title/company/location/url/direct_url/date_posted/salary/
ats/description/is_remote) so it flows through the existing
final_filter.py + telegram_notify.py pipeline unchanged.

Himalayas was evaluated and dropped: its `search`/`category`/`q` query
params don't actually filter (verified 2026-09-14 — every value returns an
effectively random slice of a ~105k-entry archive of mostly-expired
postings), so there is no reliable way to target current, relevant roles
from it today. Not integrated; revisit if their API changes.

Respect each API's own terms: Remotive asks for at most ~4 requests/day and
attribution; Remote OK asks for attribution; WWR is a public RSS feed. This
script is called by .github/workflows/remote_boards_watch.yml on a schedule
sized accordingly.
"""
import argparse
import json
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from discovery_lanes import ADJACENT_TERMS
from final_filter import eligible_location

ROLE_TERMS = re.compile(
    "|".join(re.escape(t.replace(" remote", "")) for t in ADJACENT_TERMS),
    re.I,
)
REMOTE_OK_API = "https://remoteok.com/api"
REMOTIVE_API = "https://remotive.com/api/remote-jobs"
WWR_RSS = "https://weworkremotely.com/remote-jobs.rss"
USER_AGENT = "JobFinderBot/1.0 (+https://github.com/genesishumanity/Jobfinder-GitHub-Edition)"


def _fetch_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"  WARNING: fetch failed for {url}: {type(exc).__name__}: {exc}")
        return None


def _fetch_text(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        print(f"  WARNING: fetch failed for {url}: {type(exc).__name__}: {exc}")
        return None


def role_matches(title):
    return bool(ROLE_TERMS.search(str(title or "")))


def geo_ok(location_text):
    # Delegate to final_filter's eligible_location — one geography/remote
    # source of truth instead of a second, drifting copy here. As of
    # 2026-09-15, no explicit UK/EU geography proof is required (any remote
    # role is fine, including US-based ones); only an explicit onsite/hybrid
    # tag or an explicit US-only restriction rejects.
    return eligible_location({"location": str(location_text or "")})


def fetch_remoteok():
    raw = _fetch_json(REMOTE_OK_API)
    if not isinstance(raw, list):
        return []
    jobs = []
    for row in raw:
        if not isinstance(row, dict) or not row.get("id") or not row.get("position"):
            continue
        title = str(row.get("position", ""))
        location = str(row.get("location", "") or "Worldwide")
        if not role_matches(title) or not geo_ok(location):
            continue
        jobs.append({
            "company": str(row.get("company", "")).strip(),
            "title": title.strip(),
            "location": location.strip() or "Worldwide",
            "url": str(row.get("url", "")).strip(),
            "direct_url": str(row.get("apply_url") or row.get("url", "")).strip(),
            "date_posted": str(row.get("date", ""))[:10],
            "salary": _remoteok_salary(row),
            "ats": "RemoteOK",
            "description": str(row.get("description", ""))[:4000],
            "is_remote": True,
        })
    return jobs


def _remoteok_salary(row):
    lo, hi = row.get("salary_min"), row.get("salary_max")
    if lo and hi:
        return f"${lo:,}-${hi:,}"
    return ""


def fetch_remotive():
    # As of 2026-09-14 Remotive's `search`/`category` query params return the
    # same fixed sample regardless of value (their free tier appears to have
    # been throttled down to a token listing). One plain request + client-side
    # filtering, same as RemoteOK, rather than one request per role term —
    # also keeps us well under Remotive's own "max ~4 requests/day" guidance.
    raw = _fetch_json(REMOTIVE_API)
    if not isinstance(raw, dict):
        return []
    jobs = []
    for row in raw.get("jobs", []):
        if not isinstance(row, dict):
            continue
        title = str(row.get("title", ""))
        location = str(row.get("candidate_required_location", "") or "Worldwide")
        if not role_matches(title) or not geo_ok(location):
            continue
        jobs.append({
            "company": str(row.get("company_name", "")).strip(),
            "title": title.strip(),
            "location": location.strip(),
            "url": str(row.get("url", "")).strip(),
            "direct_url": str(row.get("url", "")).strip(),
            "date_posted": str(row.get("publication_date", ""))[:10],
            "salary": str(row.get("salary", "")).strip(),
            "ats": "Remotive",
            "description": str(row.get("description", ""))[:4000],
            "is_remote": True,
        })
    return jobs


def fetch_wwr():
    xml_text = _fetch_text(WWR_RSS)
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        print(f"  WARNING: WWR RSS parse failed: {exc}")
        return []
    jobs = []
    for item in root.findall(".//item"):
        raw_title = str(item.findtext("title", "") or "")
        # WWR titles are "Company: Position".
        company, _, title = raw_title.partition(": ")
        if not title:
            title, company = raw_title, ""
        region = str(item.findtext("region", "") or "")
        country = str(item.findtext("country", "") or "")
        location = ", ".join(part for part in (country, region) if part) or "Worldwide"
        link = str(item.findtext("link", "") or "").strip()
        if not link or not role_matches(title) or not geo_ok(location):
            continue
        jobs.append({
            "company": company.strip(),
            "title": title.strip(),
            "location": location,
            "url": link,
            "direct_url": link,
            "date_posted": str(item.findtext("pubDate", "") or "")[:16],
            "salary": "",
            "ats": "WeWorkRemotely",
            "description": str(item.findtext("description", "") or "")[:4000],
            "is_remote": True,
        })
    return jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dest_json")
    args = parser.parse_args()

    remoteok_jobs = fetch_remoteok()
    remotive_jobs = fetch_remotive()
    wwr_jobs = fetch_wwr()
    jobs_by_url = {}
    for job in remoteok_jobs + remotive_jobs + wwr_jobs:
        if job["url"]:
            jobs_by_url[job["url"]] = job
    jobs = list(jobs_by_url.values())

    previous = {}
    try:
        with open(args.dest_json, encoding="utf-8") as handle:
            previous = json.load(handle)
    except (OSError, json.JSONDecodeError):
        pass
    previous_urls = {str(j.get("url", "")) for j in previous.get("jobs", []) if isinstance(j, dict)}
    new_jobs = [j for j in jobs if j["url"] not in previous_urls]

    payload = {
        "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "total": len(jobs),
        "new_count": len(new_jobs),
        "source_health": {
            "remoteok_raw": len(remoteok_jobs),
            "remotive_raw": len(remotive_jobs),
            "wwr_raw": len(wwr_jobs),
        },
        "jobs": jobs,
        "new_jobs": new_jobs,
    }
    os.makedirs(os.path.dirname(args.dest_json) or ".", exist_ok=True)
    with open(args.dest_json, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    try:
        from scrape_jobs import _merge_into_all_jobs
        _merge_into_all_jobs(jobs)
    except Exception as exc:
        print(f"WARNING: all_jobs merge failed: {type(exc).__name__}: {exc}")

    print(json.dumps({
        "remoteok_raw": len(remoteok_jobs),
        "remotive_raw": len(remotive_jobs),
        "wwr_raw": len(wwr_jobs),
        "matched": len(jobs),
        "new": len(new_jobs),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
