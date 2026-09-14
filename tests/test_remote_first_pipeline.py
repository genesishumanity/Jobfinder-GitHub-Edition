import copy

import discovery_lanes
import final_filter


ROLES = [
    "ai producer",
    "ai producing",
    "ai lead",
    "creative strategy",
    "creative lead",
    "creative director",
    "associate creative director",
    "ugc",
]


def _base_config():
    return {
        "locations": {
            "indeed": [{"location": "London, United Kingdom", "country": "GB"}],
            "google_jobs": [{"location": "London, United Kingdom", "country": "GB"}],
            "linkedin": [],
            "ziprecruiter": [],
        },
        "target_geography": {
            "locations": ["London", "Europe"],
            "exclude_us": True,
            "require_remote": True,
        },
        "location_filter": {"terms": ["london", "europe"]},
        "keywords": {"include": ROLES[:], "exclude": ["intern"]},
        "search_terms": {
            name: [] for name in (
                "linkedin", "indeed", "glassdoor", "google_jobs",
                "hiring_cafe", "ziprecruiter",
            )
        },
        "profile": {},
        "discovery_lanes": {"enabled": False},
    }


def test_focused_mode_keeps_exact_eight_role_queries():
    cfg = discovery_lanes.expand_config(copy.deepcopy(_base_config()), [])
    expected = [f"{role} remote" for role in ROLES]
    assert cfg["target_geography"]["exclude_us"] is True
    assert cfg["target_geography"]["require_remote"] is True
    assert cfg["keywords"]["include"] == ROLES
    for source in ("linkedin", "indeed", "glassdoor", "google_jobs", "ziprecruiter"):
        assert [term.casefold() for term in cfg["search_terms"][source]] == expected
    assert "project manager remote" not in cfg["search_terms"]["linkedin"]
    assert "creative producer remote" not in cfg["search_terms"]["linkedin"]


def test_delivery_gate_requires_remote_and_allowed_uk_europe_signal():
    assert final_filter.eligible_location({
        "location": "Remote - London, United Kingdom",
        "description": "AI producer role",
        "is_remote": True,
    })
    assert final_filter.eligible_location({
        "location": "Remote - Europe",
        "description": "UGC role",
        "is_remote": True,
    })
    assert not final_filter.eligible_location({
        "location": "Remote - United States",
        "description": "AI producer role",
        "is_remote": True,
    })
    assert not final_filter.eligible_location({
        "location": "Remote",
        "description": "Worldwide AI producer role",
        "is_remote": True,
    })
    assert not final_filter.eligible_location({
        "location": "London, United Kingdom",
        "description": "On-site only",
        "is_remote": False,
    })


def test_domain_gate_examples():
    from telegram_notify import domain_blocked

    assert domain_blocked({
        "title": "Pharma Project Manager",
        "description": "Requires pharma supply chain experience.",
    })
    assert not domain_blocked({
        "title": "AI Producer",
        "description": "Remote AI concept production and creative ideation.",
    })
