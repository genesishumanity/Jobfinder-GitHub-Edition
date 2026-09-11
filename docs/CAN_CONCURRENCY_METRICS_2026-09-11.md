# Delivery concurrency and query evidence — 2026-09-11
## Changes
- Added delivery_ledger.py: GitHub Contents SHA compare-and-swap reserves a hashed role/material key before Telegram sends. Only a successful claimant sends. Successful sends are finalized in the same remote ledger.
- Ledger updates are API commits, independent of each runner's stale checkout and output rebase. No credentials, chat IDs or message bodies are stored; only hashed keys, state and timestamps.
- Four Telegram watcher steps receive the existing automatic github.token via GH_TOKEN with their existing contents:write permission. No user token needed.
- Pending claims (crash, timeout or ambiguous response) are not automatically retried: counted as pending_reconciliation. This prevents duplicate attempts but cannot promise exactly-once delivery across Telegram and GitHub. A lost finalization needs reconciliation.
- Existing local dedupe remains for migration/early skips. Different title/location spellings may still be treated as different jobs.
- Added query_metrics.py and discovery experiment labels. LinkedIn normal guest searches, Indeed/Glassdoor JobSpy and Google JobSpy collect raw count, errors, unique title-relevant records, requested-geography remote matches, explicit/unknown eligibility, and incremental results against core queries and the loaded archive.
- Metrics are saved per run/attempt to output/query_metrics and committed by the four watcher workflows. Summary is visible in Actions. Hash sets permit audit without copying descriptions into reports.
- No score threshold or result cap was introduced. No model or paid service added.

## Tests and verification
- Three unittest tests passed: concurrent same-job claim (one winner), concurrent distinct-job persistence, and query overlap with unknown eligibility kept separate from explicit eligibility.
- Python compilation passed for all five affected modules.
- Remote file readback checked against tested local content.
- No live Telegram send or source scrape dispatched in this change. Query yield improvement has not yet been demonstrated.

## Measurement boundaries
- Historical novelty compares the loaded rolling all_jobs archive; it is not an unlimited lifetime history.
- Title relevance follows existing scraper gates, not independent human review.
- LinkedIn metadata can lack remote evidence before detail enrichment; early query remote counts can undercount.
- Google paid fallback paths and LinkedIn partition/backfill paths aren't attributed by this instrumentation. Primary free normal watcher paths are.
- Incremental versus core is observed within-run overlap, not a randomized causal experiment.
- New source workflow data must accumulate before accepting/rejecting query lanes.
