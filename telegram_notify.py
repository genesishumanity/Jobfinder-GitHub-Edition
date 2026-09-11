"""
Telegram delivery for newly-discovered remote opportunities.

Safe by default: this is a no-op unless both TELEGRAM_BOT_TOKEN and
TELEGRAM_CHAT_ID are GitHub Actions secrets. It never applies for the user,
uses no login/captcha bypass, and only sends direct links supplied by sources.
"""
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
    return job.get("is_remote") is True or any(word in text for word in (
        "remote", "worldwide", "anywhere", "distributed", "async", "work from home"
    ))



def target_location_allowed(job):
    """Only requested European locations; do not infer location from company HQ."""
    location = str(job.get("location", "")).lower()
    allowed = r"\b(london|amsterdam|germany|deutschland|hungary|portugal|spain|españa|berlin|munich|münchen|hamburg|frankfurt|cologne|köln|düsseldorf|stuttgart|budapest|lisbon|lisboa|porto|madrid|barcelona|valencia|sevilla|seville|malaga|málaga)\b"
    us = r"\b(united states|usa|u\.s\.|us|new york|california)\b"
    return bool(re.search(allowed, location)) and not re.search(us, location)


def identity(job):
    raw = "|".join(str(job.get(k, "")).strip().lower() for k in ("company", "title", "direct_url", "url"))
    return re.sub(r"[^a-z0-9|]", "", raw)


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
    if any(term in text for term in worldwide):
        return "✅ Uluslararası / contractor uygunluğu açık"
    if any(term in text for term in restricted):
        return "⛔ Ülke kısıtı var — UAE'den uygun görünmüyor"
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
        url,
    ])


def send(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("Telegram disabled: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are both required.")
        return False
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(API.format(token=token), data=data), timeout=20) as response:
            ok = 200 <= response.status < 300
            print(f"Telegram response: HTTP {response.status}")
            return ok
    except Exception as exc:
        print(f"Telegram delivery failed: {exc}")
        return False


def main():
    if "--test" in sys.argv:
        sys.exit(0 if send("✅ JobFinder GitHub Edition Telegram bağlantısı çalışıyor.") else 1)

    if len(sys.argv) != 2:
        print("Usage: python telegram_notify.py output/<source>_jobs.json")
        return 2
    data = load_json(sys.argv[1], {})
    new_jobs = data.get("new_jobs", [])
    if not new_jobs:
        print("No new jobs to deliver.")
        return 0

    state = load_json(STATE_PATH, {"date": "", "ids": []})
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("date") != today:
        state = {"date": today, "ids": []}

    sent_ids = set(state.get("ids", []))
    # Discovery and title filtering belong to the source scrapers. Telegram is
    # a delivery layer with the requested geography and remote gates.
    # No additional score threshold or daily cap is applied.
    candidates = [job for job in new_jobs if identity(job) not in sent_ids
                  and target_location_allowed(job) and remote_plausible(job)
                  and not international_remote_status(job).startswith("⛔")]
    candidates.sort(key=lambda job: (fit(job), bool(job.get("salary")), bool(job.get("direct_url"))), reverse=True)
    chosen = candidates

    for job in chosen:
        if send(label(job)):
            sent_ids.add(identity(job))

    state["ids"] = list(sent_ids)[-300:]
    state["date"] = today
    os.makedirs(OUTPUT, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
    print(f"Telegram: delivered {len(chosen)} new job(s); {len(sent_ids)} unique job(s) remembered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
