# Hard delivery gates correction — 2026-09-12

## Incident
Telegram delivered a New York, NY role despite the Europe-only instruction; a Berlin role requiring native German; and the same SCRL Berlin role twice during the changeover from the old delivery state to the shared ledger.

The screenshot confirms the user-facing failure. The New York card also lacked the newer date/language lines, showing at least one delivery originated from an earlier code path/run. This does not excuse it: the final delivery gate must independently reject it.

## Fix
- final_filter.py is now the delivery authority for location: must explicitly name London, Amsterdam, Germany, Hungary, Portugal, Spain or listed cities and must not contain a US location marker.
- Reject required local-language evidence: native/fluent/professional/working/business/C1/C2 German/Deutsch, Dutch/Nederlands, Hungarian/Magyar, Portuguese/Português or Spanish/Español; German as a plus remains allowed.
- Before Telegram delivery, follow the supplied direct/application link and reject only definite 404 or 410. Other network errors/rate limits remain non-definitive, so they do not create a false dead-link decision.
- Summary separately counts language and dead_link rejections.

## Verification
Offline assertions passed for New York rejection, Berlin acceptance, native-German rejection, Deutsch C1 rejection and German as a plus acceptance. Python compilation passed.

No live job page or Telegram send was run in this change. Link checking happens during subsequent workflow runs; existing already-sent cards cannot be recalled.
