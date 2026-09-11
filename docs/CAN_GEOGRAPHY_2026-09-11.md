# Can geography update — 2026-09-11

User requested London, Amsterdam, Germany, Hungary, Portugal and Spain only; no US opportunities. Remote requirement retained.

- Updated LinkedIn, Indeed, Glassdoor and Google Jobs discovery locations and Google queries.
- Added a Telegram location gate, applied to every source, using listing location rather than employer headquarters. Unknown/worldwide-only locations do not pass this strict allowlist.
- Telegram now requires remote evidence, rejects explicit hybrid/onsite arrangements and rejects the existing restricted-country label. No extra score threshold was added.
- Verified all six requested location names pass; US, New York, Paris, worldwide-only and London/United States fail; hybrid fails even with is_remote=true.

Limitations: location matching includes common city aliases but is not exhaustive. Existing remote/eligibility heuristics do not prove UAE contractor eligibility; unknown eligibility stays explicitly labelled. Live source runs and actual Telegram delivery have not been tested this turn. Existing source records were preserved.
