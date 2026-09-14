# Source health

Last audited: 2026-09-14 UTC

- LinkedIn: live on GitHub Actions; returns jobs, but guest-endpoint enrichment can make runs slow.
- Indeed: JobSpy is reachable, but the old `GB` country alias broke London queries. Remote-first config normalizes UK and should keep request volume bounded.
- Glassdoor: JobSpy calls from GitHub-hosted runners return HTTP 403 / location-not-parsed. Do not interpret a green workflow as a healthy source.
- Google Jobs: **bonus/passive, not a relied-on source.** The free JobSpy direct-scrape path is tried first and returns 0 raw rows from GitHub-hosted runners (same class of block as Glassdoor). No `SERPAPI_API_KEY`/Oxylabs key is configured, so the paid fallback never fires either. The workflow reports "success" every run while delivering nothing — do not read a green run as a healthy source. Fix requires either a SerpAPI free-tier key (~100 searches/month, no card) or accepting zero volume from this source.
- HiringCafe: removed from the active system because zero-result runs preserved stale, irrelevant cached jobs.
- Career-Ops ATS: zero-LLM direct ATS discovery lane for Greenhouse/Lever/Ashby/Workday. `careerops_portals.yml`'s title filter was out of sync with the 2026-09-14 eight-role mission (still allowed Marketing/Project/Account/Customer-Success/Implementation titles) — realigned same day.
- Remote OK: added 2026-09-14 via `remote_boards_bridge.py` — free public JSON API, no key, no scraping/IP-block risk. Verified live (99 raw postings in one pull); low match volume expected day to day since our 8-role filter is narrow and this is a single ~100-row feed, not a paginated search.
- Remotive: added 2026-09-14, same script. Its `search`/`category` query params currently return a fixed 16-job sample regardless of value (their free tier appears throttled — they advertise a paid API at $5k/mo). We fetch once and filter client-side instead of querying per role term. Treat as low-value/degraded until their API changes; kept because it's free and harmless, not because it delivers real volume right now.

A source is healthy only when it returns raw rows, not merely when its workflow exits successfully.
