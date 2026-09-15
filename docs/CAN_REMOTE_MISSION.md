# Can Öncül — Remote Jobfinder mission

## Product decision — 2026-09-09

This repository is the active JobFinder system. The old Cloudflare Worker is not the delivery path.

- Primary collection: LinkedIn, Indeed and Glassdoor watchers already present in this repository.
- Delivery: Telegram only; the dashboard remains optional and is not required for daily use.
- Candidate objective: reach £4K–£6K/month in location-independent income as quickly and safely as possible. £3.5K–£4K can be worth reviewing when credible and stable.
- Priority: fully remote international employment, contractor roles, fractional/retainer work, then high-quality short contracts with recurring potential.
- Strong role families: creative strategy, creative leadership, brand strategy, integrated creative, creative innovation/technology, AI-enabled creative work, creative production and operations, and performance/growth creative.
- Exclude commodity or unrelated roles: pure video editing, videography, graphic design, social media management, content creation, media buying, instructional systems, product/UI/UX design, customer success, medical/clinical and local-only roles.
- Remote is mandatory in practice. A listing is not treated as globally eligible merely because it says “remote”; country, contractor and timezone restrictions must be checked before applying.
- The system never auto-applies, bypasses CAPTCHA/login/MFA, invents experience, or recommends unsafe recruitment flows.
- Telegram alerts are deduplicated and capped at 10 per UTC day. They show direct source links and are leads to verify, not guarantees.

## Operating rule

Keep secrets (Telegram token, chat ID, API keys, CV text and contact data) in GitHub Actions Secrets only. Do not commit them to this public repository.


## Calibration — 2026-09-09

Initial manual runs showed that strict title matching and a 58/100 Telegram threshold produced too few leads. The discovery role set was broadened across senior creative, art direction, brand, campaigns, content and creative operations. Telegram delivery threshold is now 40/100, while the daily cap remains 10. Glassdoor returning zero listings is an upstream/source result, not an alert filter decision.


## Expansion — 2026-09-09

Discovery now covers 45 senior/adjacent titles: creative direction and strategy, art/design/visual direction, brand leadership, campaign and integrated marketing, content leadership, creative innovation/AI, production, creative services, and agency client leadership. This is discovery widening, not a claim that every role is an ideal match. Junior, commodity production and unrelated role exclusions remain in force.


## Source expansion — 2026-09-09

Google Jobs is now a Telegram delivery source alongside LinkedIn, Indeed and Glassdoor. It shares the same remote eligibility check, fit threshold and 10-per-day delivery cap.


## Throughput correction — 2026-09-09

Scheduled LinkedIn, Indeed, Glassdoor and Google Jobs workflows previously shared one concurrency group. A long LinkedIn run blocked or cancelled other sources. They now use separate source queues. Telegram discovery threshold is 25/100 and the daily delivery cap is 200 to support a high-volume discovery phase. This intentionally trades selectivity for coverage; remote and role-family exclusions remain.


## Delivery simplification — 2026-09-09

Telegram no longer applies a second score, remote-text, or daily-cap gate. Source workflows perform discovery and title/location filtering; Telegram delivers every new, deduplicated result from LinkedIn, Indeed, Glassdoor and Google Jobs. The displayed fit score remains explanatory only.


## Telegram score display correction — 2026-09-09

- Telegram is now a broad delivery layer: source scrapers decide discovery and title matching, then every new, de-duplicated result is sent.
- The old 0–100 keyword score was not a delivery decision, but it was still displayed on cards. Expanded role titles could therefore show `0/100` even when they were deliberately delivered.
- The misleading number has been removed from Telegram cards. Cards now show the source, location, salary when supplied, and the direct application link.


## International remote eligibility labels — 2026-09-09

Telegram cards now distinguish three facts that job boards frequently blur:

- `✅ Uluslararası / contractor uygunluğu açık`: the listing explicitly says worldwide, global remote, work-from-anywhere, or international/global contractor.
- `⛔ Ülke kısıtı var`: the listing explicitly requires a location or work authorization such as US-only, UK-only, EU-only, Canada-only, or Australia-only.
- `⚪ UAE/uluslararası uygunluğu ilanda net değil`: remote may be real, but the text does not prove that Can can work from UAE as an international contractor.

Unknown listings are still delivered so viable roles are not silently lost. They are not represented as confirmed UAE-compatible work.


## Final focused system audit — 2026-09-14

The production search mission is intentionally narrow and remote-first. The only approved role families are:

- AI Producer
- AI Producing
- AI Lead
- Creative Strategy
- Creative Lead
- Creative Director
- Associate Creative Director
- UGC

### Rules now enforced

- Search sources use only the eight approved role queries.
- Discovery expansion, adjacent-role rotation, company-seed expansion and generic commercial-role expansion are disabled.
- Generic project, program, account, client, marketing-operations, content-strategy and non-AI creative-producer searches are excluded.
- Remote is mandatory at delivery time.
- The allowed geography remains UK/Europe/EMEA: London/UK, Amsterdam/Netherlands, Germany, Hungary, Portugal, Spain, Europe and EMEA.
- US locations and US-only restrictions are rejected.
- Hybrid/onsite-only and local-language-required listings are rejected.
- Medical/pharma/clinical/cybersecurity and other unrelated technical-domain requirements are rejected.
- UGC is intentionally broad: it does not require an AI or creative-context phrase as long as the role is remote and passes the remaining gates.
- Telegram delivery keeps a daily cap of 10 and a minimum fit threshold of 40.
- Claude/Anthropic triage is optional; missing API/profile secrets must not stop deterministic scraping or delivery.

### Verification checklist

- config.json, discovery_lanes.py, scoring_profile.json and the focused regression suite were aligned in the same change set.
- Python compilation was run for the filter, discovery, scoring, delivery and bridge modules.
- Regression tests cover exact eight-role query sets, US rejection, ambiguous worldwide rejection, remote requirement, medical/pharma rejection and valid AI Producer/UGC examples.
- Every material change is committed to the repository so the operating rules remain auditable.

## Geography requirement relaxed — 2026-09-15

Correction from Can after a day of running the eight-role/UK-Europe-only
system live: the hard requirement that a listing explicitly name an approved
UK/Europe city or country was rejecting genuinely remote roles — including
ones he's fine with — just for lacking that specific proof. His own words:
"coğrafya kanıtı olması gerek yok, iş gelsin, ABD de olur; sadece sürekli
ABD'den geliyor diye istememiştim" (no geography proof needed, let jobs come
even from the US; the original objection was volume feeling like it was
*only* ever US, not US itself).

**Rule now:** any genuinely remote role is eligible regardless of country,
US included. Reject only:
- an explicit onsite/hybrid signal (full phrase like "hybrid only", or a
  bare "Hybrid"/"Onsite"/"In-office" tag in a structured location/
  workplace_type/work_arrangement field),
- an explicit "US only" / "must be US resident" restriction,
- required local-language fluency (unchanged from the 2026-09-12 hard
  delivery gates),
- the eight-role/geography-adjacent exclusions above (unrelated technical
  domains, non-approved role families).

This also closed a same-class bug in `careerops_bridge.py`, which had kept
its own separate, narrower geography regex (no city/country names at all)
even after `final_filter.py` was fixed the day before — a CareerOps listing
that just said "London, UK" with no literal word "remote" was being dropped
before it ever reached the fixed logic. `careerops_bridge.py` and
`remote_boards_bridge.py` now both delegate to
`final_filter.eligible_location()` instead of keeping parallel copies.

See `docs/CAN_SYSTEM_CLEANUP_2026-09-14.md` for the full change log,
including the git-push race condition found the same day.

## Daily cap removed; Gemini scoring added — 2026-09-15

Can: don't cap delivery — "tavan olmasın, ne geliyorsa o gelsin" (no cap,
whatever comes, comes; the cap was costing real opportunities). `daily_cap`
in `config.json`'s `notify` block raised from 10 to 9999 (in practice the
per-run candidate count has never approached that; this is "no cap" without
deleting the safety-valve mechanism itself).

Also: the delivery-time fit score that gates `min_fit` was always a keyword-
weighted regex formula (`notify._fit`, driven by `scoring_profile.json`) —
`triage_agent.py`'s Claude scoring never fed live delivery, only a separate
nightly dashboard pass, and it was never even running (no `ANTHROPIC_API_KEY`
configured). Added `gemini_scorer.py`: an optional real semantic re-score via
Gemini's free tier, used in `telegram_notify.py`'s `fit()` when
`GEMINI_API_KEY` + `CANDIDATE_PROFILE` secrets are set, falling back to the
keyword score on any missing config or API/parse failure — delivery never
blocks on it. Wired the two secrets into every watcher's Telegram-delivery
step (LinkedIn, Indeed, Glassdoor, Google Jobs, CareerOps ATS, Remote
Boards).

## All sources widened to a 7-day lookback — 2026-09-15

Can: "hepsi son 7 güne baksin" (everyone should look back the last 7 days).
Previously LinkedIn's regular lane looked back only 1h (hourly watcher),
Indeed/Glassdoor/ZipRecruiter/Google Jobs 24h. All widened to 7 days
(`LINKEDIN_LOOKBACK_SECONDS`, `LINKEDIN_PRIORITY_LOOKBACK_SECONDS`,
`INDEED_LOOKBACK_HOURS`, `GLASSDOOR_LOOKBACK_HOURS`,
`ZIPRECRUITER_LOOKBACK_HOURS`, `GOOGLE_JOBS_LOOKBACK_HOURS`,
`FRESH_JOB_LOOKBACK`, all in `scrape_jobs.py`). CareerOps ATS already used
`--since 7`, unchanged. Remote OK/Remotive/WWR have no date-range query
parameter to widen — they return whatever's currently live in their feed,
typically a rolling few days already.

Cross-run URL dedup means this is safe (no duplicate delivery), just more
re-scanning of the same window each hourly run — a soft cost (heavier
LinkedIn guest-endpoint load) accepted in exchange for not missing anything
posted between runs or during any downtime.

## Weekly digest rebuilt for Telegram; nightly triage removed — 2026-09-15

`weekly_digest.yml` sent to Pushover, a channel Can never configured (no
PUSHOVER_TOKEN/PUSHOVER_USER secrets) — flipping `notify.weekly_digest.enabled`
in config.json alone would have done nothing. Replaced with `weekly_digest.py`:
reads `output/telegram_notified.json` (what was actually delivered, not the
old Claude-scored `output/scores.json`, which stopped being produced once
`triage.yml` was removed), sends via Telegram. Reports delivered count,
breakdown by source, and flags any actively-scheduled source (LinkedIn,
Indeed, Glassdoor, Google Jobs, CareerOps, Remote OK, WWR — Remotive
excluded, already documented as degraded) with zero deliveries that week —
catches the "green workflow, zero data" failure mode (see SOURCE_HEALTH.md)
without needing to watch logs manually.

`.github/workflows/triage.yml` removed — its own scoring step correctly
skipped without ANTHROPIC_API_KEY, but the unconditional
`git add -f output/scores.json` in the next step failed (exit 128) on the
missing file every night. Real fix is architectural, not a patch: Gemini
scoring (2026-09-14/15) now covers this live, in the actual delivery path,
so the dead nightly workflow was removed rather than debugged.

Investigated the two dedup key formats in `telegram_notified.json` (long
hashes in `ids`, readable `company|title|location` in `records`) — not a
bug, a deliberate two-tier system: `identity()` (URL-hash) catches exact
re-scrapes, `role_key()` + a material fingerprint (salary/work_arrangement/
is_remote) detects when the same role changed and should be resent as an
update rather than skipped or silently duplicated.
