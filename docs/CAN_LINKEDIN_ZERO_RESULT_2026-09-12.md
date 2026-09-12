# LinkedIn zero-result correction — 2026-09-12

## Finding
The 03:45 UTC LinkedIn watcher read 287 cards across 212 pages but accepted zero. Exact configured title phrases pass local checks; the failure was the gap between broad LinkedIn query results and a title gate requiring exact phrase order. Examples such as Creative Strategy Lead, Strategic Creative Lead and Director of Brand Strategy were not accepted unless they exactly matched a configured phrase.

## Change
- Added an English-only LinkedIn title-family fallback. It accepts a creative/brand/content/campaign/integrated token together with strategy/strategist/director/lead/producer/technologist/innovation/operations, in either order.
- Added twelve high-signal English role variants to the LinkedIn search configuration and the configured include list.
- Removed experimental local-language title searches. The target cities remain; roles are searched in English.
- Kept existing explicit exclusion rules: junior, video editor, product/UX design, media buying and similar titles do not pass.
- LinkedIn logs now retain up to three rejected title examples per parsed page so future zero-result diagnoses have evidence.

## Verification
Offline checks passed for five intended title variants and four rejected families. No live LinkedIn fetch was dispatched; the next scheduled run will measure the effect.
