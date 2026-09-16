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


# A bare "hybrid"/"onsite" anywhere in the description used to reject the
# whole listing — real false-reject found 2026-09-16: Darkroom's "Specialist,
# Creative Strategy" explicitly said "This is a fully remote role" but got
# rejected because unrelated company-culture boilerplate further down
# mentioned "expected to work hybrid" for people near their NY/Lisbon HQs,
# not this role. Now requires the word to actually describe THIS role
# ("hybrid role", "on-site role", "X days a week in the office", etc.)
# rather than matching the bare word anywhere in a multi-paragraph posting.
HYBRID_ROLE_PATTERN = re.compile(
    r"\b(?:hybrid role|on-?site role|this (?:role|position) is hybrid|"
    r"\d+\s*days?\s*(?:a|per)?\s*week\s*(?:in|on)\s*(?:the\s*)?(?:office|site)|"
    r"\d+\s*days?\s*(?:in|on)\s*(?:the\s*)?(?:office|onsite|on-site|site))\b",
    re.I,
)


def remote_plausible(job):
    arrangement = str(job.get("work_arrangement", "")).lower()
    location = str(job.get("location", "")).lower()
    text = " ".join(str(job.get(k, "")) for k in ("location", "description", "title")).lower()
    if any(term in arrangement for term in ("on-site", "on site", "onsite", "hybrid")):
        return False
    # Bare word from structured fields (short tags, not prose) is still a
    # reliable signal; from free text it needs the stronger role-describing
    # pattern above.
    if re.search(r"\b(hybrid|on-site|onsite)\b", arrangement + " " + location):
        return False
    if re.search(r"\b(not remote|no remote)\b", text) or HYBRID_ROLE_PATTERN.search(text):
        return False
    return job.get("is_remote") is True or any(word in text for word in (
        "remote", "worldwide", "work from anywhere", "work from home", "distributed", "global", "emea"
    ))


def target_location_allowed(job):
    from final_filter import eligible_location
    return eligible_location(job)


DOMAIN_BLOCKED = re.compile(
    r"\b(?:"
    r"medical expertise|clinical expertise|pharma(?:ceutical)? experience|"
    r"medical device(?:s)? experience|healthcare domain experience|"
    r"cybersecurity|information security|security operations|security engineering|"
    r"siem|iam/pam|nist csf|iso 27001|cis controls|"
    r"pharma(?:ceutical)? (?:project|program|supply chain|manufacturing)|"
    r"clinical (?:operations|research|trials?)|"
    r"medical (?:affairs|marketing|device|equipment)|"
    r"manufacturing (?:operations|readiness|supply chain)"
    r")\b",
    re.I,
)
# The company IS a healthcare/pharma/biotech company — a much stronger, lower
# false-positive signal than scanning title/description prose, and catches
# cases with a thin/empty description (common on CareerOps ATS listings)
# that DOMAIN_BLOCKED's phrase-based check above would miss entirely. No \b
# on purpose — company names are often concatenated with no space
# ("avalerehealth"), and these particular words don't collide with unrelated
# real company-name words (e.g. "health" is not a substring of "wealth").
COMPANY_DOMAIN_BLOCKED = re.compile(
    r"health|pharma|biotech|clinical|medical|therapeutics|diagnostics|life ?sciences",
    re.I,
)
# Brand-name pharma/health-insurance/medtech companies with no generic
# health/pharma/med word in the name — the regex above can't catch these.
# Found live 2026-09-15: Humana's "Creative Director" (CareerOps/workday,
# empty description) reached Telegram because "humana" matches none of the
# generic words. Not exhaustive; add names here as they're spotted rather
# than trying to enumerate the whole industry up front.
COMPANY_BLOCKLIST = {
    "pfizer", "roche", "novartis", "merck", "gsk", "glaxosmithkline",
    "astrazeneca", "sanofi", "eli lilly", "lilly", "bristol myers squibb",
    "bristol-myers squibb", "abbvie", "amgen", "gilead", "gilead sciences",
    "biogen", "regeneron", "moderna", "johnson & johnson", "johnson and johnson",
    "humana", "unitedhealth", "unitedhealth group", "uhc", "optum", "cigna",
    "aetna", "anthem", "elevance health", "centene", "molina healthcare",
    "kaiser permanente", "stryker", "medtronic", "boston scientific",
    "becton dickinson", "bd", "abbott", "abbott laboratories", "zimmer biomet",
    "baxter", "cvs health", "cvs caremark", "walgreens boots alliance",
    "walgreens",
}


def domain_blocked(job):
    title = str(job.get("title", ""))
    description = str(job.get("description", ""))
    company = str(job.get("company", ""))
    company_norm = re.sub(r"[^a-z0-9& ]", "", company.lower()).strip()
    if company_norm in COMPANY_BLOCKLIST:
        return True
    text = f"{title} {description}"
    text = re.sub(r"\b(?:no|without|not requiring|does not require)\s+(?:any\s+)?(?:medical expertise|clinical expertise|pharma(?:ceutical)? experience|healthcare domain experience)\b", "", text, flags=re.I)
    if COMPANY_DOMAIN_BLOCKED.search(company):
        return True
    return bool(DOMAIN_BLOCKED.search(text))


# On-camera-talent / casting-call gigs get mislabeled as "UGC" jobs but are
# really "film yourself" freelance gigs (mostly Upwork), not the strategic/
# coordination UGC roles Can wants. Found live 2026-09-16: ~9 of 11 Upwork
# "UGC" postings were casting calls ("Spokesperson", "$50 per Video",
# "himself/herself", age/gender casting), while real UGC Coordinator/
# Pipeline Manager/Campaign Manager roles from real companies are fine.
# Title-only (not description) — casting language rarely shows up in prose
# by accident, but checking description too risks false-positiving on a
# legitimate UGC strategy role that happens to *describe* on-camera talent
# it will manage.
ON_CAMERA_GIG = re.compile(
    r"\b(?:spokespersons?|spokesmodels?|presenters?|actress(?:es)?|actors?|on[- ]camera|"
    r"talking head|face of the brand|"
    r"himself/herself|himself or herself|"
    r"one (?:man|woman)|paid test for|ages? \d{1,2}[-–]\d{1,2}|viral bonus)\b|"
    # `\b` doesn't work right before `$` (not a word character), so this
    # alternative is unanchored on that side.
    r"\$\d+\s*(?:per|/)\s*video\b",
    re.I,
)


def on_camera_gig_blocked(job):
    title = str(job.get("title", ""))
    return bool(ON_CAMERA_GIG.search(title))


def off_mission_role(job):
    # Hard title-level check for the eight approved role families. LinkedIn/
    # Indeed/Glassdoor/Google Jobs search queries are already narrowed to
    # these terms (config.json), but each platform's own search relevance is
    # fuzzy and surfaces off-mission titles anyway — found live 2026-09-16:
    # "Growth Marketing Manager" and "Performance Marketer" both slipped
    # through and got delivered, neither is one of the eight roles, and
    # neither would pass this check. CareerOps/Remote Boards already had this
    # exact check (discovery_lanes.ROLE_TERMS); this closes the same gap for
    # the other four sources.
    from discovery_lanes import ROLE_TERMS
    title = str(job.get("title", ""))
    return not bool(ROLE_TERMS.search(title))


def identity(job):
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
    # Optional real semantic score (Gemini) when GEMINI_API_KEY + CANDIDATE_PROFILE
    # are configured; falls back to the keyword-weighted score below on any
    # failure or when not configured, so delivery never depends on it.
    try:
        from gemini_scorer import score_job
        gemini_score = score_job(job)
        if gemini_score is not None:
            return gemini_score
    except Exception as exc:
        print(f"  WARNING: gemini_scorer unavailable, using keyword fit: {type(exc).__name__}: {exc}")

    import notify
    return notify._fit(str(job.get("title", "")), " ".join((
        str(job.get("company", "")), str(job.get("description", "")),
        str(job.get("location", "")), str(job.get("work_arrangement", "")),
    )))


def international_remote_status(job):
    text = " ".join(str(job.get(key, "")) for key in (
        "title", "location", "description", "work_arrangement"
    )).lower()

    worldwide = (
        "worldwide", "work from anywhere", "work anywhere", "anywhere in the world",
        "international contractor", "global contractor", "contractor worldwide",
        "global remote", "remote - global", "fully distributed"
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


def label(job, score=None):
    salary = str(job.get("salary", "")).strip()
    location = str(job.get("location", "")).strip() or "Remote details not stated"
    source = str(job.get("ats", "")).strip() or "source"
    url = str(job.get("direct_url", "")).strip() or str(job.get("url", "")).strip()
    score_line = f"Fit: {score:.0f}/100" if score is not None else "Fit: değerlendirilmedi"
    return "\n".join([
        "🔎 YENİ FIRSAT",
        "",
        f"{job.get('title', 'Untitled')} — {job.get('company', 'Unknown company')}",
        f"Kaynak: {source} · Yeni keşif",
        score_line,
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

    notify_cfg = config()
    try:
        min_fit = float(notify_cfg.get("telegram_min_fit", notify_cfg.get("min_fit", 0)) or 0)
    except (TypeError, ValueError):
        min_fit = 0.0
    try:
        per_run_cap = max(1, int(notify_cfg.get("daily_cap", 30) or 30))
    except (TypeError, ValueError):
        per_run_cap = 30

    data = load_json(sys.argv[1], {})
    new_jobs = data.get("new_jobs", [])
    state = load_json(STATE_PATH, {"ids": [], "records": {}})
    sent_ids = set(state.get("ids", []))
    records = state.setdefault("records", {})
    counts = dict(discovered=len(new_jobs), duplicate=0, geography=0, remote=0, restricted=0,
                  language=0, domain=0, off_mission_role=0, on_camera_gig=0, dead_link=0, low_fit=0, capped=0, delivered=0, failed=0)
    from delivery_ledger import Ledger, receipt_key
    ledger = Ledger() if os.environ.get("GITHUB_ACTIONS") == "true" else None
    counts["pending_reconciliation"] = 0
    counts["ledger_errors"] = 0

    candidates = []
    for job in new_jobs:
        if not target_location_allowed(job):
            counts["geography"] += 1
        elif not remote_plausible(job):
            counts["remote"] += 1
        elif international_remote_status(job).startswith("⛔"):
            counts["restricted"] += 1
        else:
            from final_filter import language_blocked, dead_link
            if domain_blocked(job):
                counts["domain"] += 1
            elif off_mission_role(job):
                counts["off_mission_role"] += 1
            elif on_camera_gig_blocked(job):
                counts["on_camera_gig"] += 1
            elif language_blocked(job):
                counts["language"] += 1
            elif dead_link(job):
                counts["dead_link"] += 1
            else:
                score = float(fit(job))
                if score < min_fit:
                    counts["low_fit"] += 1
                else:
                    candidates.append((score, job))

    candidates.sort(key=lambda pair: (pair[0], bool(pair[1].get("salary"))), reverse=True)
    if len(candidates) > per_run_cap:
        counts["capped"] = len(candidates) - per_run_cap
        candidates = candidates[:per_run_cap]

    for score, job in candidates:
        key, fingerprint = role_key(job), material(job)
        previous = records.get(key)
        if (previous and previous["material"] == fingerprint) or (identity(job) in sent_ids and not previous):
            counts["duplicate"] += 1
            continue
        receipt = receipt_key(key, fingerprint)
        if ledger:
            try:
                claim = ledger.claim(receipt)
            except Exception as exc:
                counts["ledger_errors"] += 1
                print("::error::Shared delivery claim failed: " + type(exc).__name__)
                continue
            if claim != "claimed":
                counts["duplicate" if claim == "sent" else "pending_reconciliation"] += 1
                continue
        text = label(job, score)
        if previous:
            text = text.replace("YENİ FIRSAT", "İLAN GÜNCELLEMESİ")
        if send(text):
            counts["delivered"] += 1
            if ledger:
                try:
                    ledger.finish(receipt)
                except Exception:
                    counts["pending_reconciliation"] += 1
                    print("::error::Telegram accepted message but ledger finalization failed; do not resend automatically")
            sent_ids.add(identity(job))
            records[key] = {"material": fingerprint, "last_sent": datetime.now(timezone.utc).isoformat()}
        else:
            counts["failed"] += 1
            if ledger:
                counts["pending_reconciliation"] += 1

    state["ids"] = sorted(sent_ids)
    state["last_run"] = {"source_file": os.path.basename(sys.argv[1]), "min_fit": min_fit, **counts}
    os.makedirs(OUTPUT, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
    print("Telegram delivery summary: " + json.dumps(counts))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("\n### Telegram delivery\n" + "\n".join(f"- {k}: {v}" for k, v in counts.items()) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
