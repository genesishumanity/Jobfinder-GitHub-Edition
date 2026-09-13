"""Hard delivery gates for Can's remote-first, English-working search."""
import re
import urllib.error
import urllib.request

REMOTE = re.compile(r"\b(remote|work from home|work-from-home|distributed|anywhere|worldwide|global|emea|europe)\b", re.I)
NOT_REMOTE = re.compile(
    r"\b(?:not remote|no remote|non[- ]remote|on[- ]site only|onsite only|office[- ]based only|"
    r"hybrid only|must work (?:from|in) (?:the )?office|remote work (?:is )?not (?:available|offered|permitted))\b",
    re.I,
)
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

# Some boards publish the whole listing in German without ever saying
# "German required". Those used to slip through the explicit-requirement gate
# above. Keep this detector conservative: strong German phrases win immediately;
# otherwise require a clear German-vs-English stop-word majority in a
# reasonably-sized listing.
_GERMAN_JOB_PHRASES = (
    "wir suchen", "deine aufgaben", "ihre aufgaben", "dein profil", "ihr profil",
    "was wir bieten", "das bieten wir", "du bringst", "sie bringen", "bewirb dich",
    "jetzt bewerben", "berufserfahrung", "abgeschlossenes studium", "kenntnisse in",
    "verantwortlich für", "unser team", "unser unternehmen", "deine rolle",
)
_GERMAN_WORDS = {
    "aber", "als", "auch", "auf", "aus", "bei", "bist", "das", "dein", "deine",
    "dem", "den", "der", "des", "die", "du", "durch", "ein", "eine", "einen",
    "einer", "für", "im", "in", "ist", "mit", "nach", "oder", "sich", "sie",
    "sind", "sowie", "und", "unser", "unsere", "von", "vor", "wir", "wird",
    "zu", "zum", "zur", "über",
}
_ENGLISH_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "is", "of", "on", "or", "our", "that", "the", "this", "to", "we", "will",
    "with", "you", "your",
}


def _looks_german(text):
    lowered = str(text or "").casefold()
    if not lowered:
        return False

    phrase_hits = sum(1 for phrase in _GERMAN_JOB_PHRASES if phrase in lowered)
    if phrase_hits >= 2:
        return True

    words = re.findall(r"[a-zà-ÿ]+", lowered)
    if len(words) < 20:
        return False

    german_hits = sum(1 for word in words if word in _GERMAN_WORDS)
    english_hits = sum(1 for word in words if word in _ENGLISH_WORDS)
    umlaut_hits = sum(lowered.count(char) for char in "äöüß")

    return (
        german_hits >= 10 and german_hits >= max(english_hits * 1.25, 10)
    ) or (
        german_hits >= 7 and umlaut_hits >= 3 and german_hits > english_hits
    )


def eligible_location(job):
    text = " ".join(str(job.get(key, "")) for key in ("location", "workplace_type", "work_arrangement", "remote", "description"))
    if NOT_REMOTE.search(text) or US_ONLY.search(text):
        return False
    # For delivery, require explicit remote/distributed evidence somewhere in the listing.
    return job.get("is_remote") is True or bool(REMOTE.search(text))


def language_blocked(job):
    text = " ".join(str(job.get(key, "")) for key in ("title", "description", "requirements"))
    return bool(LOCAL_LANGUAGE_REQUIRED.search(text)) or _looks_german(text)


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
