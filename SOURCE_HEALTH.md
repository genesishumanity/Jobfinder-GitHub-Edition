# Source health

Last audited: 2026-09-15 UTC

- LinkedIn: live on GitHub Actions; returns jobs, but guest-endpoint enrichment can make runs slow.
- Indeed: JobSpy is reachable, but the old `GB` country alias broke London queries. Remote-first config normalizes UK and should keep request volume bounded.
- Glassdoor: JobSpy calls from GitHub-hosted runners return HTTP 403 / location-not-parsed. Do not interpret a green workflow as a healthy source.
- Google Jobs: `SERPAPI_API_KEY` was added 2026-09-14 — **verified live and working**, 19 raw postings in one pull the same day. No longer bonus/passive.
- HiringCafe: removed from the active system because zero-result runs preserved stale, irrelevant cached jobs.
- Career-Ops ATS: zero-LLM direct ATS discovery lane for Greenhouse/Lever/Ashby/Workday. `careerops_portals.yml`'s title filter was out of sync with the 2026-09-14 eight-role mission (still allowed Marketing/Project/Account/Customer-Success/Implementation titles) — realigned same day. Scan width doubled 2026-09-14 (150→300 companies/ATS/run).
- **Remote OK / Remotive / WWR: NOT IP-blocked — false alarm, corrected 2026-09-15.** The weekly digest flagged these as "0 deliveries," and `remote_boards_bridge.py`'s own summary printed `remoteok_raw: 0` etc, which looked like the Glassdoor/Google-Jobs block pattern. It wasn't: those `_raw` fields were misnamed — they were actually the post-role/geo-filter *matched* count, not the true HTTP row count. Confirmed by adding real raw-row logging: the same runs that showed `remoteok_matched: 0` were fetching 100 RemoteOK rows, 15 Remotive rows, and 88 WWR rows just fine — normal traffic, no block. Zero matches across all three in the same run is just the narrow 8-role filter combined with these feeds' small size (~100-200 rows total, not a paginated search); it will vary run to run and isn't a fault. Renamed the summary fields to `*_matched` to stop this from being misread again.
- Remotive still has one real, independent issue from 2026-09-14: its `search`/`category` query params return a fixed ~15-job sample regardless of value (their free tier appears throttled — they advertise a paid API at $5k/mo). Low-value source until that changes, but not broken.

A source is healthy only when it returns raw rows, not merely when its workflow exits successfully. The weekly Telegram digest (`weekly_digest.py`) now flags any expected source with zero deliveries in the window — check it before assuming a quiet source is fine.
