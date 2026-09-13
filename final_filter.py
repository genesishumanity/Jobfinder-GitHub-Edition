"""Hard delivery gates for Can's remote-first, English-working search."""
import re
import urllib.error
import urllib.request

REMOTE = re.compile(r"\b(remote|work from home|work-from-home|distributed|anywhere|worldwide|global|emea|europe)\b", re.I)
US_ONLY = re.compile(
    r"\b(?:remote\s*[-,/ ]*\s*(?:us|usa|u\.s\.|united states)\s*only|"
    r"(?:us|usa|u\.s\.|united states)\s*[-,/ ]*\s*(?:only|residents? only|candidates? only)|"
    r"must be (?:based|located|resident) in (?:the )?(?:us|usa|u\.s\.|united states))\b",
    re.I,
)
LOCAL_LANGUAGE_REQUIRED = re.compile(
    r"\b(?:native|fluent|professional|working|full|business|c1|c2)\s+"
    r"(?:german|deutsch|dutch|nederlands|hungarian|magyar|portuguese|português|spanish|español|french|français)\b|"
    r"\b(?:german|deutsch|dutch|nederlands|hungarian|magyar|portuguese|português|spanish|español|french|français)\s+"
    r"(?:required|mandatory|essential|is required|is mandatory|c1|c2)\b",
    re.I,
)


def eligible_location(job):
    text = " ".join(str(job.get(key, "")) for key in ("location", "workplace_type", "remote", "description"))
    if US_ONLY.search(text):
        return False
    # For delivery, require explicit remote/distributed evidence somewhere in the listing.
    return bool(REMOTE.search(text))


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
            return response.status in (404, 410)
    except urllib.error.HTTPError as exc:
        return exc.code in (404, 410)
    except Exception:
        # Network/rate-limit uncertainty is not proof of a dead listing.
        return False
