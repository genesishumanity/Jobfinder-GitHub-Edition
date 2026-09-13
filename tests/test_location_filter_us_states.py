"""Regression tests for the current remote-first location strategy.

The old suite asserted that all US states were accepted and Europe was rejected.
That policy is obsolete: discovery is now remote-first and only explicit US-only
(or other non-remote) delivery restrictions should be hard blockers downstream.
"""
import pytest
from scrape_jobs import is_target_location


REMOTE_LABELS = [
    "Remote",
    "Worldwide",
    "Global Remote",
    "EMEA Remote",
    "Europe Remote",
    "Work from home",
    "Distributed team",
    "Anywhere",
]

TARGET_MARKETS = [
    "London, United Kingdom",
    "Amsterdam, Netherlands",
    "Berlin, Germany",
    "Budapest, Hungary",
    "Lisbon, Portugal",
    "Madrid, Spain",
]


@pytest.mark.parametrize("location", REMOTE_LABELS)
def test_remote_labels_are_discovery_targets(location):
    assert is_target_location(location) is True


@pytest.mark.parametrize("location", TARGET_MARKETS)
def test_existing_european_markets_remain_discovery_targets(location):
    assert is_target_location(location) is True


def test_explicit_us_only_remote_is_not_a_target():
    assert is_target_location("Remote - US only") is False
    assert is_target_location("United States candidates only") is False


def test_plain_us_location_is_not_mistaken_for_global_remote():
    assert is_target_location("Austin, Texas, United States") is False


def test_empty():
    assert is_target_location("") is False


def test_none():
    assert is_target_location(None) is False  # type: ignore[arg-type]
