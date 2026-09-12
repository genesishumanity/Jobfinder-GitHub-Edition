"""Hard delivery gates for Can's current Europe-only, English-working search."""
import re
import urllib.error
import urllib.request

TARGET = re.compile(r"\b(london|amsterdam|germany|deutschland|hungary|magyarország|portugal|spain|españa|berlin|munich|münchen|hamburg|frankfurt|cologne|köln|düsseldorf|stuttgart|budapest|lisbon|lisboa|porto|madrid|barcelona|valencia|sevilla|seville|malaga|málaga)\b", re.I)
US = re.compile(r"\b(united states|u\.s\.?|usa|new york|nyc|california|san francisco|los angeles|chicago|texas|florida|massachusetts|washington,?\s*(dc|wa)|remote,?\s*(us|usa))\b", re.I)
LOCAL_LANGUAGE_REQUIRED = re.compile(
    r"\b(?:native|fluent|professional|working|full|business|c1|c2)\s+"
    r"(?:german|deutsch|dutch|nederlands|hungarian|magyar|portuguese|português|spanish|español)\b|"
    r"\b(?:german|deutsch|dutch|nederlands|hungarian|magyar|portuguese|português|spanish|español)\s+"
    r"(?:required|mandatory|essential|is required|is mandatory|c1|c2)\b", re.I)

def eligible_location(job):
    location = str(job.get("location", ""))
    return bool(TARGET.search(location)) and not US.search(location)

def language_blocked(job):
    text = " ".join(str(job.get(key, "")) for key in ("title", "description", "requirements"))
    return bool(LOCAL_LANGUAGE_REQUIRED.search(text))

def dead_link(job):
    url = str(job.get("direct_url") or job.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return True
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "Mozilla/5.0 JobFinder link check"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return response.status == 404
    except urllib.error.HTTPError as exc:
        return exc.code in (404, 410)
    except Exception:
        # Network/rate-limit uncertainty is not proof of a dead listing.
        return False
