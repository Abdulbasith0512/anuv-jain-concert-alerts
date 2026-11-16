import pytest

from src.discovery.source_verifier import is_trusted_event_source


def test_empty_allowlist_fails_closed(monkeypatch):
    monkeypatch.delenv("TRUSTED_EVENT_SOURCE_DOMAINS", raising=False)
    assert not is_trusted_event_source({"link": "https://tickets.example.com/event"})


def test_exact_allowlisted_domain_is_trusted(monkeypatch):
    monkeypatch.setenv("TRUSTED_EVENT_SOURCE_DOMAINS", "tickets.example.com")
    assert is_trusted_event_source({"publisher_url": "https://tickets.example.com/event"})


def test_subdomain_of_allowlisted_domain_is_trusted(monkeypatch):
    monkeypatch.setenv("TRUSTED_EVENT_SOURCE_DOMAINS", "example.com")
    assert is_trusted_event_source({"link": "https://events.example.com/show"})


def test_lookalike_suffix_is_not_trusted(monkeypatch):
    monkeypatch.setenv("TRUSTED_EVENT_SOURCE_DOMAINS", "example.com")
    assert not is_trusted_event_source({"link": "https://example.com.attacker.test/event"})


def test_http_is_not_trusted(monkeypatch):
    monkeypatch.setenv("TRUSTED_EVENT_SOURCE_DOMAINS", "example.com")
    assert not is_trusted_event_source({"link": "http://example.com/event"})


def test_malformed_url_is_not_trusted(monkeypatch):
    monkeypatch.setenv("TRUSTED_EVENT_SOURCE_DOMAINS", "example.com")
    assert not is_trusted_event_source({"link": "not a url"})


def test_city_only_is_not_returned_as_venue():
    from src.discovery.event_extractor import extract_venue
    assert extract_venue("Anuv Jain concert at Mumbai") is None


def test_possessive_city_prefix_is_removed_from_venue():
    from src.discovery.event_extractor import extract_venue
    assert extract_venue("Anuv Jain show at Mumbai’s Mehboob Studio") == "Mehboob Studio"
