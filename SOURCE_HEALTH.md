# Source health

Last audited: 2026-09-13 UTC

- LinkedIn: live on GitHub Actions; returns jobs, but guest-endpoint enrichment can make runs slow.
- Indeed: JobSpy is reachable, but the old `GB` country alias broke London queries. Remote-first config normalizes UK and should keep request volume bounded.
- Glassdoor: JobSpy calls from GitHub-hosted runners return HTTP 403 / location-not-parsed. Do not interpret a green workflow as a healthy source.
- HiringCafe: removed from the active system because zero-result runs preserved stale, irrelevant cached jobs.
- Career-Ops ATS: added as a zero-LLM direct ATS discovery lane for Greenhouse/Lever/Ashby/Workday.

A source is healthy only when it returns raw rows, not merely when its workflow exits successfully.
