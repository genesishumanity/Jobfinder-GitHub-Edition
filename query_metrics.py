"""Per-query evidence. Counts are observed matches, not interview predictions."""
import atexit
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROWS = {}
EXPERIMENTS = set()
BASELINE = set()

def record(source, query, location, raw, jobs, error=False):
    from telegram_notify import identity, remote_plausible, target_location_allowed, international_remote_status
    key = (source, query, location)
    row = ROWS.setdefault(key, dict(source=source, query=query, location=location,
        lane="experimental" if any(query == q or query.startswith(q + " jobs ") for q in EXPERIMENTS) else "core",
        raw=0, errors=0, matches={}, eligible=[]))
    row["raw"] += raw
    row["errors"] += int(error)
    for job in jobs:
        ident = identity(job)
        geographic = target_location_allowed(job)
        remote = remote_plausible(job)
        status = international_remote_status(job)
        row["matches"][ident] = {"target_remote": geographic and remote,
            "eligibility": "restricted" if status.startswith("⛔") else "explicit" if status.startswith("✅") else "unknown"}

def report():
    core = {key for r in ROWS.values() if r["lane"] == "core" for key in r["matches"]}
    output = []
    for row in ROWS.values():
        matches = row["matches"]
        good = {k for k,v in matches.items() if v["target_remote"] and v["eligibility"] != "restricted"}
        output.append({k:v for k,v in row.items() if k not in ("matches", "eligible")} | {
            "unique_relevant": len(matches), "target_remote_not_restricted": len(good),
            "explicit_international": sum(v["target_remote"] and v["eligibility"] == "explicit" for v in matches.values()),
            "eligibility_unknown": sum(v["target_remote"] and v["eligibility"] == "unknown" for v in matches.values()),
            "incremental_vs_core_this_run": len(good-core) if row["lane"] == "experimental" else None,
            "historically_new_target_remote": len(good-BASELINE),
            "new_incremental_vs_core": len(good-core-BASELINE) if row["lane"] == "experimental" else None,
            "job_hashes": sorted(matches)})
    return output

def flush():
    if not ROWS:
        return
    root = Path(__file__).resolve().parent / "output" / "query_metrics"
    root.mkdir(parents=True, exist_ok=True)
    run = os.environ.get("GITHUB_RUN_ID", "local") + "-" + os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    path = root / (run + ".json")
    payload = {"at": datetime.now(timezone.utc).isoformat(), "queries": report(),
        "scope": "Observed title-matched results; incremental counts compare this run only, not historical novelty. Eligibility unknown is not confirmed suitable."}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("\n### Query evidence\n|Query|Raw|Relevant|Target remote*|Extra vs core|Errors|\n|---|---:|---:|---:|---:|---:|\n")
            for r in payload["queries"]:
                q = r["query"].replace("|", "/")
                f.write(f"|{q}|{r['raw']}|{r['unique_relevant']}|{r['target_remote_not_restricted']}|{r['incremental_vs_core_this_run']}|{r['errors']}|\n")
            f.write("\n*Includes unknown work eligibility; inspect explicit_international in JSON.\n")

atexit.register(flush)
