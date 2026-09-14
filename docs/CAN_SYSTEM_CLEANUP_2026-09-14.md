# System cleanup & hardening — 2026-09-14

Retroactive log of a full cleanup/audit pass with Claude, covering everything
from "why am I getting no good jobs" through source expansion and a
production bug found along the way. Written after the fact so the reasoning
is auditable, matching the existing `docs/CAN_*.md` convention.

## 1. Root-cause: zero deliveries despite real matches

Investigation of a `delivered: 0` day traced to `final_filter.py`'s
`eligible_location()`, which required the literal word remote/distributed/
worldwide/europe/emea to appear in listing text, even when the job's own
`location` field already named an approved city/country (London, Berlin,
Madrid, etc). Two genuine Creative Strategist roles in Berlin/Munich were
rejected purely because their listing never used the word "remote", while
unrelated senior/marketing roles in the same run passed because the word
happened to appear elsewhere in their text.

**Fix:** an explicit approved-geography location now counts as remote
evidence on its own, still subject to the existing NOT_REMOTE/US_ONLY/
US_LOCATION rejections. Commit `500e22dc`.

## 2. Dead weight removed

- Deleted 5 US-only watcher workflows that ran daily and could never pass
  the delivery gate anyway (mission is UK/Europe remote-first, and
  `final_filter.py` rejects every US location): `calcareers_watch.yml`,
  `csucareers_watch.yml`, `localgov_watch.yml`, `usajobs_watch.yml`,
  `ziprecruiter_watch.yml`.
- Deleted `docs/deep-dive/` — stale April/May notes from an earlier phase,
  unrelated to the current mission.
- Commit `ff6bd1a2`.

## 3. CareerOps ATS role filter was out of sync with the mission

`careerops_portals.yml`'s title filter still allowed Marketing Manager,
Project Manager, Account Manager, Customer Success Manager, Implementation
Manager and similar generic titles — these were never removed when the
mission was narrowed to eight approved roles on 2026-09-14 (see
`CAN_REMOTE_MISSION.md`'s "Final focused system audit"). This lane could
have delivered off-mission roles via Telegram. Trimmed to the eight approved
families and close aliases. Commit `49764869`.

## 4. New free sources: Remote OK + Remotive

Added `remote_boards_bridge.py` + `.github/workflows/remote_boards_watch.yml`:
pulls Remote OK's public JSON feed (no key, no scraping/IP-block risk — the
feed is a single ~100-row rolling list) and Remotive's public feed, filters
both client-side by the same eight role terms and geography rules the rest
of the pipeline uses, normalizes into the standard job schema, and flows
through the existing `final_filter.py` / `telegram_notify.py` pipeline
unchanged.

Found along the way: Remotive's `search`/`category` query params currently
return a fixed 16-job sample regardless of value — their free tier appears
throttled (they advertise a paid API at $5k/mo). Adjusted to fetch once and
filter client-side instead of one request per role term, which also respects
their own "max ~4 requests/day" guidance. Documented in `SOURCE_HEALTH.md`.
Commit `49764869`.

## 5. Google Jobs: documented as bonus/passive, not fixed

Confirmed the free JobSpy direct-scrape path (tried before any paid
fallback) returns 0 raw rows from GitHub-hosted runners — same class of
block as Glassdoor's 403s. No `SERPAPI_API_KEY`/Oxylabs key is configured,
so the paid fallback never fires either. The workflow reports "success"
every run while silently delivering nothing. Left as-is (no code change);
`SOURCE_HEALTH.md` now says so explicitly so a green run is never mistaken
for a healthy one. Real fix, if wanted later, is a SerpAPI free-tier key
(~100 searches/month, no card required).

## 6. Production bug found while adding source #4: git push race condition

Adding `remote_boards_watch.yml` triggered it and `careerops_ats_watch.yml`
via the same push (both have path-based push triggers). Both tried to
commit to the shared `output/all_jobs.json` and `output/telegram_notified.json`
in the same window. CareerOps lost the race: its persist step hit a real
rebase conflict and failed, discarding that run's delivery state — real risk
of the same job being re-notified on Telegram next run.

**Root cause:** `linkedin_watch.yml`, `indeed_watch.yml`, `glassdoor_watch.yml`
and `google_jobs_watch.yml` already used `git pull --rebase -X ours origin main`
to resolve exactly this kind of conflict automatically. `careerops_ats_watch.yml`
never had it — an existing gap, not something this cleanup introduced — and
`remote_boards_watch.yml` inherited the same gap because it was templated off
`careerops_ats_watch.yml`.

**Fix:** both workflows now use the same `-X ours` pattern already proven
elsewhere. Also moved `remote_boards_watch.yml`'s schedule from `:7` to `:52`
past the hour, clear of every other watcher's slot, to reduce how often two
watchers are mid-run at the same time — this narrows the collision window but
doesn't eliminate it (push-triggered runs ignore cron offsets, which is
exactly how today's collision happened), which is why the `-X ours` fix is
the real protection. Commit `00e708d5`.

**Verified:** re-triggered the exact same push-collision scenario (CareerOps
ATS Watcher + Remote Boards Watcher firing on the same push) after the fix —
both completed successfully this time (`careerops_ats_watch` run `34845343195`,
conclusion `success`).

## Verification summary

- 94/94 tests pass throughout (Python 3.12 locally; CI uses 3.11/3.12).
- `final_filter.py` fix re-run against the actual raw 8-job batch that
  produced the 2026-09-14 `delivered: 0` incident: both real Creative
  Strategist matches now pass.
- `remote_boards_bridge.py` role/geo logic checked against synthetic cases
  (US-only correctly rejected, worldwide/UK/remote correctly accepted) and
  run live against both real APIs.
- Every change pushed to `main` and confirmed green in GitHub Actions before
  moving to the next step.
