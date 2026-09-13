"""Convert Career-Ops reverse-ATS JSON into JobFinder's source snapshot format."""
import argparse
import json
import os
import re
from datetime import datetime, timezone

REMOTE = re.compile(r"\b(remote|worldwide|global|anywhere|distributed|emea|europe)\b", re.I)
NOT_REMOTE = re.compile(r"\b(not remote|no remote|non[- ]remote|hybrid only|on[- ]site only|onsite only)\b", re.I)
US_REMOTE_ONLY = re.compile(r"\bremote\s*[-,/ ]+\s*(?:us|usa|u\.s\.|united states)\s*$", re.I)


def read_json(path, fallback):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return fallback


def remote_candidate(offer):
    text = " ".join(str(offer.get(k, "")) for k in ("title", "location", "note"))
    if NOT_REMOTE.search(text) or US_REMOTE_ONLY.search(text.strip()):
        return False
    return bool(REMOTE.search(text))


def normalize(offer):
    source = str(offer.get("source", "career-ops")).replace("-full", "")
    return {
        "company": str(offer.get("company", "")).strip(),
        "title": str(offer.get("title", "")).strip(),
        "location": str(offer.get("location", "")).strip(),
        "url": str(offer.get("url", "")).strip(),
        "direct_url": str(offer.get("url", "")).strip(),
        "date_posted": offer.get("postedAt") or "",
        "salary": "",
        "ats": f"CareerOps/{source}",
        "description": str(offer.get("note", "") or ""),
        "is_remote": True,
        "work_arrangement": "remote",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_json")
    parser.add_argument("dest_json")
    args = parser.parse_args()

    raw = read_json(args.raw_json, {})
    offers = raw.get("offers", []) if isinstance(raw, dict) else []
    jobs = []
    seen = set()
    for offer in offers:
        if not isinstance(offer, dict) or not remote_candidate(offer):
            continue
        job = normalize(offer)
        if not job["url"] or not job["title"] or job["url"] in seen:
            continue
        seen.add(job["url"])
        jobs.append(job)

    previous = read_json(args.dest_json, {})
    previous_urls = {str(j.get("url", "")) for j in previous.get("jobs", []) if isinstance(j, dict)}
    new_jobs = [j for j in jobs if j["url"] not in previous_urls]

    health = {
        "sources": raw.get("sources", []),
        "companies_available": raw.get("companiesAvailable", 0),
        "companies_scanned": raw.get("companiesScanned", 0),
        "unreachable_boards": raw.get("unreachableBoards", 0),
        "stopped_by_outage": bool(raw.get("stoppedByOutage", False)),
        "dataset_status": raw.get("datasetStatus", {}),
        "postings_kept_upstream": raw.get("postingsKept", 0),
        "remote_jobs_kept": len(jobs),
    }
    payload = {
        "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "total": len(jobs),
        "new_count": len(new_jobs),
        "source_health": health,
        "jobs": jobs,
        "new_jobs": new_jobs,
    }
    os.makedirs(os.path.dirname(args.dest_json) or ".", exist_ok=True)
    with open(args.dest_json, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    # Feed the same cumulative master used by triage/dashboard without duplicating scraper logic.
    try:
        from scrape_jobs import _merge_into_all_jobs
        _merge_into_all_jobs(jobs)
    except Exception as exc:
        print(f"WARNING: all_jobs merge failed: {type(exc).__name__}: {exc}")

    print(json.dumps({"careerops_ats": health, "new_jobs": len(new_jobs)}, ensure_ascii=False))
    if health["companies_scanned"] == 0:
        print("::warning::Career-Ops ATS lane scanned zero companies; treat this run as degraded, not healthy-empty.")


if __name__ == "__main__":
    main()
