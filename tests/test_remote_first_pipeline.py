import copy

import careerops_bridge
import discovery_lanes
import final_filter


def _base_config():
    return {
        "locations": {
            "indeed": [{"location": "London, United Kingdom", "country": "GB"}],
            "google_jobs": [{"location": "London, United Kingdom", "country": "GB"}],
            "linkedin": [],
            "ziprecruiter": [],
        },
        "target_geography": {"locations": ["London"], "exclude_us": True, "require_remote": True},
        "location_filter": {"terms": ["london"]},
        "keywords": {"include": ["creative strategist"], "exclude": ["customer success", "intern"]},
        "search_terms": {name: [] for name in ("linkedin", "indeed", "glassdoor", "google_jobs", "hiring_cafe", "ziprecruiter")},
        "profile": {},
        "discovery_lanes": {"enabled": False},
    }


def test_remote_first_repairs_jobspy_country_and_expands_adjacent_roles():
    cfg = discovery_lanes.expand_config(copy.deepcopy(_base_config()), [])
    assert cfg["locations"]["indeed"][0]["country"] == "UK"
    remote_countries = {
        x["country"] for x in cfg["locations"]["indeed"]
        if x.get("location") == "Remote"
    }
    assert {"UK", "Netherlands", "Germany", "Hungary", "Portugal", "Spain"} <= remote_countries
    assert "customer success" not in cfg["keywords"]["exclude"]
    assert "customer success manager" in cfg["keywords"]["include"]
    assert "project manager remote" in cfg["search_terms"]["linkedin"]
    assert cfg["target_geography"]["exclude_us"] is False


def test_delivery_gate_is_remote_first_not_europe_city_first():
    assert final_filter.eligible_location({
        "location": "Worldwide",
        "description": "Fully remote team working globally",
    })
    assert final_filter.eligible_location({
        "location": "Dubai",
        "is_remote": True,
        "description": "Work from anywhere",
    })
    assert not final_filter.eligible_location({
        "location": "Berlin",
        "description": "On-site only. Remote work is not available.",
    })
    assert not final_filter.eligible_location({
        "location": "Remote - United States only",
        "description": "US candidates only",
    })


def test_careerops_bridge_keeps_global_remote_and_drops_onsite():
    assert careerops_bridge.remote_candidate({
        "title": "Creative Strategist - Remote",
        "location": "Worldwide",
    })
    assert careerops_bridge.remote_candidate({
        "title": "Program Manager - Remote",
        "location": "EMEA",
    })
    assert not careerops_bridge.remote_candidate({
        "title": "Creative Strategist",
        "location": "London (on-site only)",
    })


def test_delivery_blocks_german_language_listing_but_keeps_english_germany_role():
    assert final_filter.language_blocked({
        "title": "Creative Strategist",
        "description": (
            "Wir suchen eine kreative Person für unser Team. Deine Aufgaben umfassen die Entwicklung "
            "von Kampagnen und die Zusammenarbeit mit unseren Kunden. Du bringst mehrjährige "
            "Berufserfahrung mit und verfügst über sehr gute Kenntnisse im Bereich Marketing. "
            "Was wir bieten: flexible Arbeitszeit, ein internationales Team und eine spannende Tätigkeit."
        ),
    })
    assert not final_filter.language_blocked({
        "title": "Creative Strategist - Germany Remote",
        "description": (
            "We are looking for a creative strategist to join our remote team in Germany. "
            "You will own campaign strategy, work with international clients, and collaborate in English. "
            "German language skills are a plus but are not required."
        ),
    })
