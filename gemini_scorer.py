"""Optional Gemini-backed semantic fit scoring for live Telegram delivery.

The real delivery-time score (the one that gates min_fit in telegram_notify.py)
has always come from notify.py's _fit() — a keyword-weighted regex formula
driven by scoring_profile.json. It has no semantic understanding: it can't
tell a genuinely well-matched role from one that just happens to contain the
right keywords.

This module adds an optional real LLM re-score using Gemini's free tier
(no card required — https://aistudio.google.com/apikey). Dormant by default:
returns None (caller falls back to the keyword score) whenever GEMINI_API_KEY
or CANDIDATE_PROFILE isn't configured, or on any API/parse error — this must
never block or slow down deterministic delivery, matching the project's
existing rule for optional AI features (see CLAUDE.md / CAN_REMOTE_MISSION.md).

Called per-candidate in telegram_notify.py, i.e. only for jobs that already
survived every geography/role/language/domain gate — call volume per run is
small (usually 0-10), well inside Gemini Flash's free-tier rate limits
(~15 req/min, ~1500 req/day as of 2026-09).
"""
import json
import os
import urllib.error
import urllib.request

from triage_agent import _read_first

# "-latest" alias tracks Google's current stable Flash model automatically,
# so this doesn't go stale the way a pinned version (e.g. "gemini-2.0-flash")
# does — that exact pin 404'd in production 2026-09-16, silently, for as long
# as Gemini scoring has existed, because it had been retired. Override via
# env var if a specific pin is ever needed again.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)
TIMEOUT_SECONDS = 15

PROMPT_TEMPLATE = """You are scoring one job listing for a specific candidate. Be honest and specific — this gates a real notification, not a generic ATS score.

CANDIDATE PROFILE:
{profile}

JOB LISTING:
Title: {title}
Company: {company}
Location: {location}
Description:
{description}

Score how well this specific listing matches this specific candidate's real profile and goals, from 0 to 100. Judge genuine fit (role, seniority, remote/AI-creative alignment, realistic route to success) — not just keyword overlap.

Respond with ONLY a JSON object, no other text: {{"score": <integer 0-100>, "reason": "<one sentence>"}}"""


def _gemini_api_key():
    return os.environ.get("GEMINI_API_KEY", "").strip()


def score_job(job):
    """Returns a 0-100 float score, or None if not configured / on any failure."""
    api_key = _gemini_api_key()
    if not api_key:
        return None
    profile = _read_first("CANDIDATE_PROFILE", "candidate_profile.md")
    if not profile.strip():
        print("  WARNING: GEMINI_API_KEY is set but CANDIDATE_PROFILE is not — falling back to keyword fit")
        return None

    prompt = PROMPT_TEMPLATE.format(
        profile=profile.strip()[:4000],
        title=str(job.get("title", "")),
        company=str(job.get("company", "")),
        location=str(job.get("location", "")),
        description=str(job.get("description", ""))[:6000],
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 200},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{GEMINI_URL}?key={api_key}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text[4:] if text.lower().startswith("json") else text
        parsed = json.loads(text)
        score = max(0.0, min(100.0, float(parsed["score"])))
        reason = str(parsed.get("reason", ""))[:200]
        print(f"  Gemini score: {score:.0f} — {reason}")
        return score
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        print(f"  WARNING: Gemini scoring failed, falling back to keyword score: HTTPError {exc.code}: {detail or exc}")
        return None
    except (
        urllib.error.URLError,
        TimeoutError,
        KeyError,
        IndexError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"  WARNING: Gemini scoring failed, falling back to keyword score: {type(exc).__name__}: {exc}")
        return None
