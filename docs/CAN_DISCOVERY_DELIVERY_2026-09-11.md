# Can discovery and delivery — 2026-09-11
## Implemented
- Fixed legacy is_target_location: previously explicitly rejected Germany/Spain/Portugal etc and accepted US states. Scraper and delivery now share the requested geography.
- Preserved core searches; rotate up to four extra queries per source per hour: description phrases, freelance/fractional/retainer, translated titles, and companies observed in target-location creative listings.
- Google explicit queries also receive the experimental lanes (search_terms alone was bypassed).
- No AI/API service added. No daily cap or score gate added.
- Added local-language title acceptance. Telegram reports explicit language requirement excerpts and supplied posting dates; unknown stays unknown.
- Delivery state no longer resets at midnight or truncates to 300 IDs. Canonical URL tracking cleanup plus company/title/location keys suppress repeated cards; salary/work-arrangement changes generate updates.
- Count actual successful deliveries, failures and geography/remote/eligibility/duplicate rejection reasons in Actions summary and persisted last_run. Failed sends aren't marked delivered. Successful sends can still be committed after another send fails.
- Reject explicit not-remote/hybrid language; restriction evidence takes precedence over worldwide wording. This remains heuristic, not verified work authorization.

## Verification
Python compilation passed for scraper, discovery module and Telegram module.
Offline mocked checks passed: all six target regions, US exclusions, tracking URL deduplication, repeated runs, changed salary update, contradictory remote/UK-only text, bounded query additions and seed-company query.
No live board scan or Telegram message was dispatched. Increased qualified yield is NOT yet demonstrated.

## Limits / next validation
- Description-derived queries require descriptions in all_jobs; otherwise configured hypothesis queries rotate. Seed selection uses creative title plus target location, not a proven hiring-quality judgment.
- Company query searches other roles at observed companies. Independent peer-company discovery/direct career-page crawling is not implemented here.
- Concurrent source workflows still share telegram_notified.json. Git rebase can lose concurrent state; repository-wide atomic delivery coordination remains outstanding.
- Historic legacy IDs cannot all be converted without original job records; cross-source identity can still differ by title/location spelling.
- Remote eligibility and language are evidence labels, not legal eligibility verification.
- Compare incremental unique, relevant and eligible results against core searches before expanding the query budget. Do not claim live improvement from offline tests.
