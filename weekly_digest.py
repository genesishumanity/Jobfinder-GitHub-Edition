"""Weekly Telegram digest: what actually got delivered in the last N days.

Reuses telegram_notify.py's real delivery record (output/telegram_notified.json)
rather than the old Claude-scored output/scores.json, which no longer gets
produced now that the nightly triage workflow is gone (2026-09-15) — this
digest reports on what actually happened, not a scoring pass that doesn't run.
"""
import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(ROOT, "output")
NOTIFIED_PATH = os.path.join(OUTPUT, "telegram_notified.json")
ALL_JOBS_PATH = os.path.join(OUTPUT, "all_jobs.json")


def load_json(path, fallback):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return fallback


def role_key(job):
    return "|".join(re.sub(r"\s+", " ", str(job.get(k, "")).strip().casefold()) for k in ("company", "title", "location"))


# The 8 approved role families (see discovery_lanes.ADJACENT_TERMS / docs/
# CAN_REMOTE_MISSION.md). Order matters — checked top to bottom, first match
# wins, so more specific terms (e.g. "associate creative director") are
# listed before the shorter terms they contain ("creative director").
ROLE_CATEGORIES = [
    ("AI Producer", re.compile(r"ai\s*produc(?:er|ing)", re.I)),
    ("AI Lead", re.compile(r"\bai\s*lead\b", re.I)),
    ("Associate Creative Director", re.compile(r"associate\s*creative\s*director", re.I)),
    ("Creative Director", re.compile(r"\bcreative\s*director\b", re.I)),
    ("Creative Strategy", re.compile(r"\bcreative\s*strateg", re.I)),
    ("Creative Lead", re.compile(r"\bcreative\s*lead\b", re.I)),
    ("UGC", re.compile(r"\bugc\b", re.I)),
]


def categorize_title(title):
    text = str(title or "")
    for label, pattern in ROLE_CATEGORIES:
        if pattern.search(text):
            return label
    return "Diğer"


# Friendly Turkish labels for the raw `ats` source codes stored on each job.
SOURCE_LABELS = {
    "LinkedIn": "LinkedIn",
    "Indeed": "Indeed",
    "Glassdoor": "Glassdoor",
    "GoogleJobs": "Google Jobs",
    "RemoteOK": "Remote OK",
    "Remotive": "Remotive",
    "WeWorkRemotely": "We Work Remotely",
    "unknown": "Diğer",
}


def _source_label(raw_source):
    prefix = str(raw_source or "unknown").split("/")[0]
    if prefix == "CareerOps":
        # e.g. "CareerOps/workday" -> "CareerOps (Workday)"
        parts = str(raw_source).split("/", 1)
        sub = parts[1].capitalize() if len(parts) > 1 and parts[1] else ""
        return f"CareerOps ({sub})" if sub else "CareerOps"
    return SOURCE_LABELS.get(prefix, prefix)


def build_digest(days=7):
    notified = load_json(NOTIFIED_PATH, {"records": {}})
    all_jobs = load_json(ALL_JOBS_PATH, {"jobs": []})
    job_by_key = {role_key(j): j for j in all_jobs.get("jobs", [])}

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    delivered = []
    for key, record in notified.get("records", {}).items():
        sent_at = record.get("last_sent", "")
        try:
            sent_dt = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if sent_dt >= cutoff:
            matched = job_by_key.get(key)
            title = matched.get("title") if matched else key.split("|")[1] if "|" in key else key
            delivered.append({
                "title": title or "?",
                "source": matched.get("ats", "unknown") if matched else "unknown",
            })

    if not delivered:
        return f"📊 Haftalık JobFinder özeti (son {days} gün)\n\nBu hafta hiç ilan gönderilmedi."

    by_source = {}
    for d in delivered:
        label = _source_label(d["source"])
        by_source[label] = by_source.get(label, 0) + 1
    source_lines = [f"  • {label}: {count}" for label, count in sorted(by_source.items(), key=lambda x: -x[1])]

    # Flag any actively-scheduled source that delivered nothing at all this
    # window — a source can run "successfully" every hour while quietly
    # returning zero (Glassdoor/Google Jobs both did this in the past; see
    # SOURCE_HEALTH.md), and that's easy to miss without watching logs.
    expected_sources = ("LinkedIn", "Indeed", "Glassdoor", "GoogleJobs", "CareerOps", "RemoteOK", "WeWorkRemotely")
    seen_prefixes = {str(d["source"]).split("/")[0] for d in delivered}
    silent_sources = [_source_label(s) for s in expected_sources if s not in seen_prefixes]

    lines = [
        f"📊 Haftalık JobFinder özeti (son {days} gün)",
        "",
        f"Toplam {len(delivered)} ilan gönderildi.",
        "",
        "Kaynaklara göre:",
    ]
    lines.extend(source_lines)
    if silent_sources:
        lines.append("")
        lines.append(f"⚠️ Bu hafta hiç ilan getirmeyen kaynaklar: {', '.join(silent_sources)} — bir bakmakta fayda var.")

    by_role = {}
    for d in delivered:
        label = categorize_title(d["title"])
        by_role[label] = by_role.get(label, 0) + 1
    role_lines = [f"  • {label}: {count}" for label, count in sorted(by_role.items(), key=lambda x: -x[1])]

    lines.append("")
    lines.append("En çok gelen roller:")
    lines.extend(role_lines)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    message = build_digest(args.days)
    print(message)

    from telegram_notify import send
    ok = send(message)
    if not ok:
        print("WARNING: weekly digest Telegram send failed or is not configured.")


if __name__ == "__main__":
    main()
