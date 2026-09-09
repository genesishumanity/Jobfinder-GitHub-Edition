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
    if "on-site" in arrangement or "on site" in arrangement:
        return False
    return job.get("is_remote") is True or any(word in text for word in (
        "remote", "worldwide", "anywhere", "distributed", "async", "work from home"
    ))


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


def label(job):
    salary = str(job.get("salary", "")).strip()
    location = str(job.get("location", "")).strip() or "Remote details not stated"
    source = str(job.get("ats", "")).strip() or "source"
    url = str(job.get("direct_url", "")).strip() or str(job.get("url", "")).strip()
    return "\n".join([
        "🟢 REMOTE FIRSAT",
        "",
        f"{job.get('title', 'Untitled')} — {job.get('company', 'Unknown company')}",
        f"Uygunluk: {fit(job)}/100 · Kaynak: {source}",
        f"Konum: {location}",
        f"Maaş: {salary or 'belirtilmemiş'}",
        "Not: ülke/contractor uygunluğunu başvurmadan önce doğrula.",
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
    # deliberately a delivery layer: every newly-discovered, not-yet-sent job
    # reaches Can without a second score, remote-text, or daily-cap gate.
    candidates = [job for job in new_jobs if identity(job) not in sent_ids]
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
