"""Fast hourly LinkedIn runner.

The normal scraper keeps deep pagination for backfills and diagnostics. The hourly
watcher only needs the freshest page for each rotating remote-first term/geo; it
runs every hour, so deep pagination adds latency and rate-limit risk without
meaningful freshness benefit.
"""
import scrape_jobs as jobs

_original_search = jobs._linkedin_search


def _hourly_search(terms, lookback_seconds, geos=None, max_results=500):
    # One LinkedIn guest-result page (10 cards) per active term/geo. Discovery
    # lanes already rotate terms and regions hourly, while always retaining the
    # global Remote lane.
    return _original_search(
        terms,
        lookback_seconds,
        geos=geos,
        max_results=min(int(max_results or 10), 10),
    )


jobs._linkedin_search = _hourly_search

result = jobs.scrape_linkedin_recent()
before = len(result)
result = [j for j in result if jobs.is_target_location(j.get("location", ""))]
print(f"📍 Location filter: {before} → {len(result)} roles")
jobs.save_linkedin_results(result)
