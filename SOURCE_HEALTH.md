# Source health

Last audited: 2026-09-15 UTC

- LinkedIn: live on GitHub Actions; returns jobs, but guest-endpoint enrichment can make runs slow.
- Indeed: JobSpy is reachable, but the old `GB` country alias broke London queries. Remote-first config normalizes UK and should keep request volume bounded.
- Glassdoor: JobSpy calls from GitHub-hosted runners return HTTP 403 / location-not-parsed. Do not interpret a green workflow as a healthy source.
- Google Jobs: `SERPAPI_API_KEY` was added 2026-09-14 — **verified live and working**, 19 raw postings in one pull the same day. No longer bonus/passive.
- HiringCafe: removed from the active system because zero-result runs preserved stale, irrelevant cached jobs.
- Career-Ops ATS: zero-LLM direct ATS discovery lane for Greenhouse/Lever/Ashby/Workday. `careerops_portals.yml`'s title filter was out of sync with the 2026-09-14 eight-role mission (still allowed Marketing/Project/Account/Customer-Success/Implementation titles) — realigned same day. Scan width doubled 2026-09-14 (150→300 companies/ATS/run).
- **Remote OK / Remotive / WWR: regressed to the Glassdoor/Google-Jobs failure class — 2026-09-15.** Added 2026-09-14 as "free, no scraping/IP-block risk" (verified working that day: 99 RemoteOK rows, real WWR RSS). Every GitHub Actions run since early 2026-09-15 (checked 05:00, 09:01, 13:00, 14:33, 14:37 UTC) returns 0 raw rows from all three, silently — no exception, no HTTP error surfaced. Same URLs return real data (100 RemoteOK rows, valid Remotive payload, 840KB WWR RSS) from a non-GitHub-Actions IP the same day. Conclusion: GitHub-hosted runner IPs are now being soft-blocked by these APIs too — the "no IP-block risk" assumption from 2026-09-14 was wrong. Added explicit WARNING logging (`remote_boards_bridge.py`) so this shows up in run logs instead of looking like a healthy empty run; the weekly digest's "0 deliveries this source" flag is what surfaced it. No fix available without a proxy or a paid alternative — same category as Glassdoor.
- Remotive specifically also has a second, independent issue from 2026-09-14: its `search`/`category` query params return a fixed 16-job sample regardless of value (their free tier appears throttled — they advertise a paid API at $5k/mo). Moot right now since the IP-block above means even that degraded 16-job sample isn't reaching GitHub Actions.

A source is healthy only when it returns raw rows, not merely when its workflow exits successfully. The weekly Telegram digest (`weekly_digest.py`) now flags any expected source with zero deliveries in the window — check it before assuming a quiet source is fine.
