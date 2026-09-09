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
