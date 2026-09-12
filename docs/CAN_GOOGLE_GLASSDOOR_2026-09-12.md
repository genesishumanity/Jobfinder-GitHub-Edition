# Google cache and Glassdoor repair — 2026-09-12

## Evidence
- Google Jobs executed 22 queries successfully but returned zero raw rows. With no API fallback configured, the prior output retained four stale US/off-target jobs.
- Glassdoor executed 36 calls and each logged location not parsed. The installed python-jobspy 1.1.82 documentation lists Glassdoor support for UK, Netherlands, Germany and Spain; its country enum has no Glassdoor domain for Hungary or Portugal. The previous config also used GB rather than the library's required country name UK.

## Changes
- Google fallback cache is now scoped through the current target geography and role title filter before it is kept. Out-of-scope US cache entries disappear on the next zero-data Google run.
- Glassdoor location config now uses London/UK, Amsterdam/Netherlands, Berlin/Germany, Madrid/Spain. Hungary and Portugal are intentionally not sent to this JobSpy source; LinkedIn, Indeed and Google queries retain them.

## Verification and limitation
- Offline cache check passed: US environmental result removed; Berlin and Spain creative roles kept.
- No live Glassdoor query was dispatched. The next scheduled Glassdoor run validates whether the supported city/country values solve location parsing. If Glassdoor still fails, its shared GitHub Actions IP path is the blocker, not a successful but empty search.
