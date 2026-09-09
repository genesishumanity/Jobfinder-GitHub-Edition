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
