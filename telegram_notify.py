"""
Telegram delivery for newly-discovered remote opportunities.

Safe by default: this is a no-op unless both TELEGRAM_BOT_TOKEN and
TELEGRAM_CHAT_ID are GitHub Actions secrets. It never applies for the user,
uses no login/captcha bypass, and only sends direct links supplied by sources.
"""
import email.utils
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
    from final_filter import milan_local
    if milan_local(job):
        return True
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


# Freelance gig marketplaces and "talent pool" recruiting platforms — not real
# employers. Found live 2026-09-17 auditing a week of Telegram deliveries:
# Upwork micro-gigs ("Cavalier Dog Owner UGC Long Term!", "Set up a WhatsApp
# AI Lead-Qualification System") and marketplace accounts posting under their
# own brand as if they were the employer (Jobgether, HireLATAM, Jobs for
# Lebanon) made up a large share of low-quality deliveries — exactly the
# "pool-building"/"subscriber-collecting" middleman junk Can flagged. These
# platforms structurally aren't the remote job Can wants regardless of how
# well the title matches, so blocked by company name (Upwork/Fiverr/
# Freelancer's own domains are already caught by untrusted_source()'s
# allowlist below — this only needs to catch marketplace accounts posting
# under their own brand on an otherwise-trusted domain like LinkedIn).
GIG_MARKETPLACE_COMPANIES = {
    "jobgether", "hirelatam", "crossing hurdles",
}
# Junk site crackdown 2026-09-17: Can reported quality collapsed, most
# deliveries from generic reposting/aggregator/subscription-harvest sites.
# Switched from blocklisting known junk to allowlisting known-good sources:
# LinkedIn, Indeed, the ATS platforms CareerOps scans, and the Remote
# Boards themselves. Blocks everything else (bebee, jobleads, learn4good,
# mediabistro, monster, tealhq, showbizjobs, vaia, ziprecruiter, etc.) by
# default instead of chasing each junk domain one at a time.
ALLOWED_SOURCE_DOMAINS = re.compile(
    r"(?:^|\.)linkedin\.com$|"
    r"(?:^|\.)indeed\.com$|"
    r"(?:^|\.)greenhouse\.io$|"
    r"(?:^|\.)lever\.co$|"
    r"(?:^|\.)ashbyhq\.com$|"
    r"(?:^|\.)myworkdayjobs\.com$|"
    r"(?:^|\.)remoteok\.com$|"
    r"(?:^|\.)remotive\.com$|"
    r"(?:^|\.)weworkremotely\.com$|"
    r"(?:^|\.)himalayas\.app$|"
    r"(?:^|\.)jobicy\.com$|"
    r"(?:^|\.)ziprecruiter\.com$|"
    r"(?:^|\.)glassdoor\.com$",
    re.I,
)


def untrusted_source(job):
    # "url" is the discovery listing (indeed.com, linkedin.com, ...);
    # "direct_url" is often the employer's own apply link on their own ATS
    # domain (found live 2026-09-17 — checking direct_url first wrongly
    # blocked genuine Indeed listings whose apply link pointed off-site).
    # Trust is about the source we found it on, so check "url" first.
    url = str(job.get("url") or job.get("direct_url") or "")
    netloc = urllib.parse.urlsplit(url).netloc.lower()
    return not bool(ALLOWED_SOURCE_DOMAINS.search(netloc))


def gig_marketplace_blocked(job):
    company = str(job.get("company", ""))
    company_norm = re.sub(r"[^a-z0-9& ]", "", company.lower()).strip()
    return company_norm in GIG_MARKETPLACE_COMPANIES or company_norm.startswith("jobs for ")


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


# Title-level blockers for sources that skip the scraper's keywords.exclude
# (remote boards, CareerOps): junior/intern roles, Italian protected-category
# (L.68/99) vacancies, and roles that require a local language in the title.
OFF_MISSION_TITLE = re.compile(
    r"\b(?:intern|internship|stage|stagista|tirocinio|stajyer|trainee|junior|jr|working student|"
    r"categoria protetta|l\.?\s?68/99|"
    r"(?:dutch|german|french|spanish|swedish|norwegian|danish|finnish|polish)[- ]speaking)\b",
    re.I,
)


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
    return not bool(ROLE_TERMS.search(title)) or bool(OFF_MISSION_TITLE.search(title))


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
    from final_filter import milan_local
    if milan_local(job):
        return "📍 Milano/İstanbul yerel rol — ofis/hibrit de uygun"
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
        return "⛔ Ülke kısıtı var — İtalya'dan uygun görünmüyor"
    if any(term in text for term in worldwide):
        return "✅ Uluslararası / contractor uygunluğu açık"
    return "⚪ İtalya/uluslararası uygunluğu ilanda net değil"


# Precision layer (2026-09-28). A dry run over two weeks of listings showed
# about half of what passed the gates above was still unusable for a Turkish
# citizen targeting remote work or Milan/Istanbul:
# - titles outside the craft (copywriting, SAP, media buying, UX/UI, 3D,
#   visual merchandising, on-camera UGC creators) or tied to a US city/language
# - "Anywhere" listings whose text is a US employment package (401(k),
#   US work authorization, US time-zone hours, US Hispanic market)
# - listings whose location names only countries he can't work from.
WRONG_ROLE_TITLE = re.compile(
    # Mandate 2026-09-29 down-rank list: execution-only craft, social/media
    # management, engineering and junior/coordinator roles.
    r"\b(?:graphic designer|(?:senior |lead )?(?:creative |visual |motion )?designer|videographer|camera operator|video editor|social media manager|"
    r"software engineer|ml engineer|machine learning engineer|developer|coordinator|junior|intern|"
    r"copy(?:writer|writing)?|sap|media buyer|visual merchandising|ux|ui|uxui|3d|"
    r"bilingual|creator remote|dog creator|onsite|on-site|applied ai|"
    r"la|nyc|new york|los angeles|san francisco|chicago|austin)\b",
    re.I,
)
# UGC titles are creator/influencer gigs unless they carry a senior craft word
# ("Creative Lead (Social & UGC)" stays).
UGC_TITLE = re.compile(r"\bugc\b|user[- ]generated", re.I)
UGC_SENIOR = re.compile(r"\b(?:lead|director|strateg\w*|producer|head)\b", re.I)
US_EMPLOYMENT = re.compile(
    r"401\(k\)|\bW-?2\b|"
    r"authori[sz]ed to work (?:for any employer )?in the (?:US|U\.S\.?|United States)|"
    r"\b(?:PST|PT|EST|ET|CST|MST) hours\b|US Hispanic|"
    r"health,? dental,? (?:and )?vision|dental,? (?:and )?vision|hourly pay range|tier 1 cities",
    re.I,
)
# Places a location may name and still be workable: remote-open regions,
# Turkey (home) and Italy (target).
WORKABLE_PLACE = re.compile(
    r"worldwide|anywhere|global|international|emea|europe|european union|"
    r"turkey|türkiye|turkiye|istanbul|i̇stanbul|ankara|izmir|italy|italia|milan|milano|lombard",
    re.I,
)
GENERIC_LOCATION = re.compile(r"\b(?:remote|hybrid|work from home|wfh|flexible|multiple locations)\b", re.I)


# Required relocation anywhere but Italy/Turkey, and required languages the
# candidate doesn't speak (English and Turkish are fine).
RELOCATION_TITLE = re.compile(r"relocat\w*\s+to\s+(?!italy|milan|turkey|türkiye|istanbul)\w+", re.I)
REQUIRED_LANGUAGE = re.compile(
    r"(?:fluent|fluency|native|proficien\w*|business[- ]level)\s+(?:in\s+)?(?:\w+\s+and\s+)?"
    r"(?:italian|german|french|spanish|dutch|arabic|portuguese|polish)\b"
    r"|\b(?:italian|german|french|spanish|dutch|arabic|portuguese|polish)\s+(?:is\s+)?(?:required|mandatory|essential|native)",
    re.I,
)


# Craft-led art direction and design-leadership titles (mandate down-ranks
# specialist art-direction and pure design roles); concept-led AD stays.
CRAFT_TITLE = re.compile(
    r"\bart director\b|\bdesign\b.*\b(?:director|head|lead)\b|\b(?:director|head|lead)\b.*\bdesign\b",
    re.I,
)
# A listing written in Italian expects an Italian speaker even if it never
# says "Italian required" (found 2026-10-02: Simbiosi Creative).
ITALIAN_TEXT = re.compile(
    r"\b(?:cerchiamo|requisiti|esperienza|offriamo|lavorerai|stretto contatto|il nostro|la nostra|"
    r"candidatura|conoscenza|competenze|responsabilità)\b",
    re.I,
)


def precision_blocked(job):
    """Return a reason string when a listing can't be a fit, else None."""
    title = str(job.get("title", ""))
    if RELOCATION_TITLE.search(title):
        return "country_restricted"
    description = str(job.get("description", ""))
    if REQUIRED_LANGUAGE.search(description) or len(set(m.lower() for m in ITALIAN_TEXT.findall(description))) >= 3:
        return "language_required"
    if CRAFT_TITLE.search(title) and not re.search(r"conceptual|creative technolog", title, re.I):
        return "wrong_role"
    if WRONG_ROLE_TITLE.search(title) or (UGC_TITLE.search(title) and not UGC_SENIOR.search(title)):
        return "wrong_role"
    if US_EMPLOYMENT.search(str(job.get("description", ""))):
        return "us_employment"
    location = str(job.get("location", ""))
    leftover = re.sub(r"[^\w]+", " ", GENERIC_LOCATION.sub(" ", location)).strip()
    if leftover and not WORKABLE_PLACE.search(location):
        return "country_restricted"
    return None


# Signals that a role closes fast: contract/freelance hiring skips most of a
# full-time loop, worldwide contractor roles have no visa step, and applying
# in the first days of a posting beats the applicant pile.
CONTRACT_TERMS = re.compile(
    r"\b(?:contract(?:or)?|freelance|part[- ]time|fixed[- ]term|temporary|project[- ]based|retainer)\b",
    re.I,
)
FRESH_DAYS = 3


def _posted_date(job):
    raw = str(job.get("posted_at") or job.get("date_posted") or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw[:10]).date()
    except ValueError:
        pass
    try:
        return email.utils.parsedate_to_datetime(raw).date()
    except (TypeError, ValueError):
        return None


def landing_signals(job, today=None):
    """Return the fast-landing tags for a job, strongest first."""
    tags = []
    text = " ".join(str(job.get(k, "")) for k in ("title", "job_type", "work_arrangement", "description"))
    if CONTRACT_TERMS.search(text):
        tags.append("Kontrat/freelance")
    if international_remote_status(job).startswith("✅"):
        tags.append("Worldwide")
    posted = _posted_date(job)
    today = today or datetime.now(timezone.utc).date()
    if posted and 0 <= (today - posted).days <= FRESH_DAYS:
        tags.append(f"Yeni (≤{FRESH_DAYS} gün)")
    return tags


# Role brief (WebGPT job search mandate, 2026-09-29). Rule-based and derived
# only from the listing text: it never invents experience, metrics or contacts.
STRETCH_TITLE = re.compile(
    r"\b(?:associate creative director|acd|creative director|head of creative|"
    r"executive creative|group creative director|vp\b|chief)",
    re.I,
)
FIT_SIGNALS = (
    ("creative strategy", r"creative strateg"),
    ("concept development", r"\bconcept|ideation"),
    ("storytelling", r"storytell|narrative"),
    ("treatments/storyboards", r"storyboard|treatment"),
    ("film/video production", r"\bfilm\b|video|production"),
    ("generative AI", r"generative|gen ?ai|\bai\b|midjourney|runway|kling"),
    ("rapid prototyping", r"prototyp|experiment"),
    ("brand strategy", r"brand strateg|positioning"),
    ("integrated campaigns", r"integrated|campaign"),
    ("pitching", r"\bpitch"),
    ("zero-to-one", r"zero[- ]to[- ]one|0 ?(?:to|→) ?1|from scratch|build(?:ing)? the"),
    ("creative systems/ops", r"creative (?:ops|operations|systems|automation)|workflow"),
)
GAP_SIGNALS = (
    ("long agency tenure", r"\b(?:[7-9]|1\d)\+? years|agency (?:background|experience) (?:is )?required"),
    ("large paid-media budget", r"media budget|ad spend|\$\d+[mk]\+? (?:in )?(?:annual )?(?:spend|budget)|roas"),
    ("people management", r"manage (?:a )?team of|direct reports|people management"),
    ("specialist craft depth", r"expert in (?:after effects|cinema 4d|figma)|motion design expert"),
)
PORTFOLIO_ANGLES = (
    (r"generative|gen ?ai|\bai\b|previs|prototyp", "AI previs case (Atorie / Dolce Glow)"),
    (r"brand|strateg|positioning|campaign", "strategy-led concept (Atorie 'good enough.')"),
    (r"video|film|production|social|ugc|content", "produced social/video work (MADA)"),
    (r"product|system|workflow|automation|tool", "live AI product built solo (INSPIRE)"),
)


def role_brief(job):
    title = str(job.get("title", ""))
    text = " ".join(str(job.get(k, "")) for k in ("title", "description")).lower()
    stretch = bool(STRETCH_TITLE.search(title))
    fits = [name for name, pat in FIT_SIGNALS if re.search(pat, text, re.I)][:3]
    gaps = [name for name, pat in GAP_SIGNALS if re.search(pat, text, re.I)]
    angle = next((a for pat, a in PORTFOLIO_ANGLES if re.search(pat, text, re.I)), "strongest concept case")
    if stretch:
        priority = "Stretch"
    elif landing_signals(job) or len(fits) >= 2:
        priority = "Apply now"
    else:
        priority = "Targeted outreach"
    owner = "Head of Creative / Creative Director" if re.search(r"creative|brand|art", title, re.I) else "Head of Marketing / Growth"
    return {"priority": priority, "fits": fits, "gaps": gaps, "angle": angle, "owner": owner}


PRIORITY_RANK = {"Apply now": 2, "Targeted outreach": 1, "Stretch": 0}


def brief_lines(job):
    b = role_brief(job)
    return "\n".join([
        f"🎯 Öncelik: {b['priority']}",
        "✓ Uyum: " + (", ".join(b["fits"]) or "ilan metni kısa, doğrula"),
        "△ Eksik/risk: " + (", ".join(b["gaps"]) or "belirgin değil"),
        f"📁 Göster: {b['angle']}",
        f"✉️ Kime: {b['owner']} · Açı: 15 dk tek sayfa fikir + {b['angle'].split(' (')[0]}",
    ])


# One-tap LinkedIn people searches for whoever owns the hire. These are plain
# search URLs the user opens in their own account: nothing is scraped and no
# message is sent automatically.
CONTACT_SEARCHES = (
    ("Creative lead", "head of creative OR creative director OR head of brand"),
    ("Recruiter", "recruiter OR talent acquisition"),
    ("Founder", "founder OR CEO OR CMO"),
)


def contact_links(job):
    company = re.sub(r"\s+", " ", str(job.get("company", ""))).strip()
    if not company or company.casefold() in {"unknown company", "confidential"}:
        return ""
    links = []
    for name, query in CONTACT_SEARCHES:
        q = urllib.parse.quote(f'"{company}" {query}')
        links.append(f"{name}: https://www.linkedin.com/search/results/people/?keywords={q}")
    return "👤 Kime yaz:\n" + "\n".join(links)


def label(job, score=None):
    salary = str(job.get("salary", "")).strip()
    location = str(job.get("location", "")).strip() or "Remote details not stated"
    source = str(job.get("ats", "")).strip() or "source"
    url = str(job.get("direct_url", "")).strip() or str(job.get("url", "")).strip()
    score_line = f"Fit: {score:.0f}/100" if score is not None else "Fit: değerlendirilmedi"
    tags = landing_signals(job)
    return "\n".join([
        "⚡ HIZLI SONUÇ ADAYI" if tags else "🔎 YENİ FIRSAT",
        "⚡ " + " · ".join(tags) if tags else "",
        f"{job.get('title', 'Untitled')} — {job.get('company', 'Unknown company')}",
        f"Kaynak: {source} · Yeni keşif",
        score_line,
        f"Konum: {location}",
        international_remote_status(job),
        f"Maaş: {salary or 'belirtilmemiş'}",
        "Yayın: " + str(job.get("posted_at") or job.get("date_posted") or "belirtilmemiş"),
        language_status(job),
        brief_lines(job),
        url,
        contact_links(job),
    ]).rstrip()


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
                  language=0, domain=0, gig_marketplace=0, untrusted_source=0, off_mission_role=0, on_camera_gig=0, dead_link=0, low_fit=0, capped=0, delivered=0, failed=0)
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
            if untrusted_source(job):
                counts["untrusted_source"] += 1
            elif domain_blocked(job):
                counts["domain"] += 1
            elif gig_marketplace_blocked(job):
                counts["gig_marketplace"] += 1
            elif off_mission_role(job):
                counts["off_mission_role"] += 1
            elif on_camera_gig_blocked(job):
                counts["on_camera_gig"] += 1
            elif precision_blocked(job):
                reason = precision_blocked(job)
                counts[reason] = counts.get(reason, 0) + 1
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

    # Fast-landing roles first (contract, worldwide, fresh), then fit.
    candidates.sort(key=lambda pair: (
        PRIORITY_RANK[role_brief(pair[1])["priority"]],
        len(landing_signals(pair[1])), pair[0], bool(pair[1].get("salary")),
    ), reverse=True)
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
