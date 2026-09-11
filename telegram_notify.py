"""
Telegram delivery for newly-discovered remote opportunities.

Safe by default: this is a no-op unless both TELEGRAM_BOT_TOKEN and
TELEGRAM_CHAT_ID are GitHub Actions secrets. It never applies for the user,
uses no login/captcha bypass, and only sends direct links supplied by sources.
"""
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(ROOT, "output")
STATE_PATH = os.path.join(OUTPUT, "telegram_notified.json")
CONFIG_PATH = os.path.join(ROOT, "config.json")
API = "https://api.telegram.org/bot{token}/sendMessage"


def load_json(path, fallback):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return fallback


def config():
    return load_json(CONFIG_PATH, {}).get("notify", {})


def remote_plausible(job):
    arrangement = str(job.get("work_arrangement", "")).lower()
    text = " ".join(str(job.get(k, "")) for k in ("location", "description", "title")).lower()
    if any(term in arrangement for term in ("on-site", "on site", "onsite", "hybrid")):
        return False
    if re.search(r"\b(not remote|no remote|hybrid|on-site|onsite)\b", text):
        return False
    return job.get("is_remote") is True or any(word in text for word in (
        "remote", "worldwide", "work from anywhere", "work from home"
    ))



def target_location_allowed(job):
    from discovery_lanes import target_location
    return target_location(job.get("location", ""))


def identity(job):
    # Prefer the employer link; strip tracking without discarding job identifiers.
    url = str(job.get("direct_url") or job.get("url") or "").strip()
    parts = urllib.parse.urlsplit(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query)
             if not k.lower().startswith("utm_") and k.lower() not in ("trk", "ref", "source")]
    canonical = urllib.parse.urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urllib.parse.urlencode(sorted(query)), ""))
    raw = canonical or "|".join(str(job.get(k, "")).strip().casefold() for k in ("company", "title", "location"))
    return hashlib.sha256(raw.encode()).hexdigest()


def role_key(job):
    return "|".join(re.sub(r"\s+", " ", str(job.get(k, "")).strip().casefold()) for k in ("company", "title", "location"))


def material(job):
    return "|".join(str(job.get(k, "")).strip() for k in ("salary", "work_arrangement", "is_remote"))


def fit(job):
    # Reuse the configurable fit model; custom scoring_profile.json prevents
    # environmental/toxicology terms from leaking into this installation.
    import notify
    return notify._fit(str(job.get("title", "")), " ".join((
        str(job.get("company", "")), str(job.get("description", "")),
        str(job.get("location", "")), str(job.get("work_arrangement", "")),
    )))


def international_remote_status(job):
    """Conservative eligibility label; never infer UAE eligibility from 'remote' alone."""
    text = " ".join(str(job.get(key, "")) for key in (
        "title", "location", "description", "work_arrangement"
    )).lower()

    worldwide = (
        "worldwide", "work from anywhere", "work anywhere", "anywhere in the world",
        "international contractor", "global contractor", "contractor worldwide",
        "global remote", "remote - global"
    )
    restricted = (
        "u.s. only", "us only", "usa only", "remote, us", "united states only",
        "must be based in the us", "right to work in the us", "us work authorization",
        "uk only", "united kingdom only", "right to work in the uk",
        "eu only", "european union only", "must be based in canada",
        "canada only", "australia only"
    )
    if any(term in text for term in restricted):
        return "⛔ Ülke kısıtı var — UAE'den uygun görünmüyor"
    if any(term in text for term in worldwide):
        return "✅ Uluslararası / contractor uygunluğu açık"
    return "⚪ UAE/uluslararası uygunluğu ilanda net değil"


def label(job):
    salary = str(job.get("salary", "")).strip()
    location = str(job.get("location", "")).strip() or "Remote details not stated"
    source = str(job.get("ats", "")).strip() or "source"
    url = str(job.get("direct_url", "")).strip() or str(job.get("url", "")).strip()
    return "\n".join([
        "🔎 YENİ FIRSAT",
        "",
        f"{job.get('title', 'Untitled')} — {job.get('company', 'Unknown company')}",
        f"Kaynak: {source} · Yeni keşif",
        f"Konum: {location}",
        international_remote_status(job),
        f"Maaş: {salary or 'belirtilmemiş'}",
        "Yayın: " + str(job.get("posted_at") or job.get("date_posted") or "belirtilmemiş"),
        language_status(job),
        url,
    ])


def language_status(job):
    text = str(job.get("description", ""))
    requirements = re.findall(r"[^.!?\n]*(?:German|Dutch|Hungarian|Portuguese|Spanish|English)[^.!?\n]*(?:required|mandatory|fluent|native)[^.!?\n]*|[^.!?\n]*(?:required|mandatory|fluent|native)[^.!?\n]*(?:German|Dutch|Hungarian|Portuguese|Spanish|English)[^.!?\n]*", text, re.I)
    return "Dil şartı: " + ("; ".join(requirements)[:350] if requirements else "ilan metninden doğrulanamadı")


def send(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("Telegram disabled: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are both required.")
        return False
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(API.format(token=token), data=data), timeout=20) as response:
            ok = 200 <= response.status < 300 and json.load(response).get("ok") is True
            print(f"Telegram response: HTTP {response.status}")
            return ok
    except Exception as exc:
        print(f"Telegram delivery failed: {type(exc).__name__}")
        return False


def main():
    if "--test" in sys.argv:
        sys.exit(0 if send("✅ JobFinder GitHub Edition Telegram bağlantısı çalışıyor.") else 1)

    if len(sys.argv) != 2:
        print("Usage: python telegram_notify.py output/<source>_jobs.json")
        return 2
    data = load_json(sys.argv[1], {})
    new_jobs = data.get("new_jobs", [])
    state = load_json(STATE_PATH, {"ids": [], "records": {}})
    sent_ids = set(state.get("ids", []))
    records = state.setdefault("records", {})
    counts = dict(discovered=len(new_jobs), duplicate=0, geography=0, remote=0, restricted=0, delivered=0, failed=0)
    candidates = []
    for job in new_jobs:
        if not target_location_allowed(job):
            counts["geography"] += 1
        elif not remote_plausible(job):
            counts["remote"] += 1
        elif international_remote_status(job).startswith("⛔"):
            counts["restricted"] += 1
        else:
            candidates.append(job)
    candidates.sort(key=lambda j: (fit(j), bool(j.get("salary"))), reverse=True)
    for job in candidates:
        key, fingerprint = role_key(job), material(job)
        previous = records.get(key)
        if (previous and previous["material"] == fingerprint) or (identity(job) in sent_ids and not previous):
            counts["duplicate"] += 1
            continue
        text = label(job)
        if previous:
            text = text.replace("YENİ FIRSAT", "İLAN GÜNCELLEMESİ")
        if send(text):
            counts["delivered"] += 1
            sent_ids.add(identity(job))
            records[key] = {"material": fingerprint, "last_sent": datetime.now(timezone.utc).isoformat()}
        else:
            counts["failed"] += 1
    state["ids"] = sorted(sent_ids)
    state["last_run"] = {"source_file": os.path.basename(sys.argv[1]), **counts}
    os.makedirs(OUTPUT, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
    print("Telegram delivery summary: " + json.dumps(counts))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("\n### Telegram delivery\n" + "\n".join(f"- {k}: {v}" for k,v in counts.items()) + "\n")
    return 0  # Persist successful sends even when another delivery failed.


if __name__ == "__main__":
    raise SystemExit(main())

