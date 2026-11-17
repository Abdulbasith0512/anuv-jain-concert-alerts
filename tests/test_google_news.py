from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from src.discovery import google_news


class FakeResponse:
    def __init__(self, content=b"<rss/>", error=None, headers=None, status_code=None):
        self.content = content
        self.error = error
        self.headers = headers or {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.error:
            raise self.error


def entry(link="https://publisher.example/story", title="Anuv Jain upcoming concert"):
    return {
        "title": title,
        "link": link,
        "summary": "Anuv Jain will perform live at a concert.",
        "source": {"title": "Example News"},
        "published": "Tue, 17 Nov 2026 08:00:00 GMT",
    }


def feed(entries):
    return SimpleNamespace(entries=entries, bozo=False, bozo_exception=None)


def patch_common(monkeypatch, entries):
    monkeypatch.setattr(google_news.requests, "get", lambda *a, **k: FakeResponse())
    monkeypatch.setattr(google_news.feedparser, "parse", lambda content: feed(entries))
    monkeypatch.setattr(google_news, "is_relevant_event", lambda title, description: True)
    monkeypatch.setattr(
        google_news, "classify_event",
        lambda title, description: {"status": "potential_upcoming", "reason": "test"},
    )
    monkeypatch.setattr(google_news.time, "sleep", lambda seconds: None)


def test_build_feed_url_includes_query_and_region():
    region = {"hl": "en-IN", "gl": "IN", "ceid": "IN:en"}
    params = parse_qs(urlsplit(google_news._build_feed_url('"Anuv Jain" concert', region)).query)
    assert params["q"] == ['"Anuv Jain" concert']
    assert params["hl"] == ["en-IN"]
    assert params["gl"] == ["IN"]


def test_fetch_events_searches_every_query_and_region(monkeypatch):
    calls = []
    monkeypatch.setattr(
        google_news.requests, "get",
        lambda url, **kwargs: (calls.append(url) or FakeResponse()),
    )
    monkeypatch.setattr(google_news.feedparser, "parse", lambda content: feed([entry()]))
    monkeypatch.setattr(google_news, "is_relevant_event", lambda title, description: True)
    monkeypatch.setattr(google_news, "classify_event", lambda title, description: {"status": "potential_upcoming", "reason": "test"})
    monkeypatch.setattr(google_news.time, "sleep", lambda seconds: None)

    results = google_news.fetch_events()
    assert len(calls) == len(google_news.SEARCH_QUERIES) * len(google_news.SEARCH_REGIONS)
    assert len(results) == 1
    assert len(results[0]["discovery_queries"]) == len(google_news.SEARCH_QUERIES)
    assert len(results[0]["discovery_regions"]) == len(google_news.SEARCH_REGIONS)


def test_fetch_events_preserves_publisher_metadata(monkeypatch):
    patch_common(monkeypatch, [entry()])
    result = google_news.fetch_events()[0]
    assert result["source"] == "Example News"
    assert result["published"] == "Tue, 17 Nov 2026 08:00:00 GMT"
    assert result["status"] == "potential_upcoming"


def test_fetch_events_filters_irrelevant_entries(monkeypatch):
    entries = [entry("https://publisher.example/yes", "Anuv Jain upcoming concert"), entry("https://publisher.example/no", "Anuv Jain interview")]
    patch_common(monkeypatch, entries)
    monkeypatch.setattr(google_news, "is_relevant_event", lambda title, description: "concert" in title.lower())
    results = google_news.fetch_events()
    assert len(results) == 1
    assert results[0]["link"].endswith("/yes")


def test_fetch_events_retries_temporary_network_failure(monkeypatch):
    calls = 0
    sleeps = []
    def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("temporary network failure")
        return FakeResponse()
    monkeypatch.setattr(google_news.requests, "get", fake_get)
    monkeypatch.setattr(google_news.feedparser, "parse", lambda content: feed([entry()]))
    monkeypatch.setattr(google_news, "is_relevant_event", lambda title, description: True)
    monkeypatch.setattr(google_news, "classify_event", lambda title, description: {"status": "potential_upcoming", "reason": "test"})
    monkeypatch.setattr(google_news.time, "sleep", lambda seconds: sleeps.append(seconds))
    assert google_news.fetch_events()
    assert calls == len(google_news.SEARCH_QUERIES) * len(google_news.SEARCH_REGIONS) + 1
    assert google_news.RETRY_BACKOFF_SECONDS in sleeps


def test_fetch_events_retries_http_429(monkeypatch):
    calls = 0
    sleeps = []
    def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            response = FakeResponse(headers={"Retry-After": "3"}, status_code=429)
            error = requests.HTTPError("429 too many requests", response=response)
            raise error
        return FakeResponse()
    monkeypatch.setattr(google_news.requests, "get", fake_get)
    monkeypatch.setattr(google_news.feedparser, "parse", lambda content: feed([entry()]))
    monkeypatch.setattr(google_news, "is_relevant_event", lambda title, description: True)
    monkeypatch.setattr(google_news, "classify_event", lambda title, description: {"status": "potential_upcoming", "reason": "test"})
    monkeypatch.setattr(google_news.time, "sleep", lambda seconds: sleeps.append(seconds))
    assert google_news.fetch_events()
    assert calls == len(google_news.SEARCH_QUERIES) * len(google_news.SEARCH_REGIONS) + 1
    assert 3.0 in sleeps


def test_fetch_events_raises_if_all_requests_fail(monkeypatch):
    monkeypatch.setattr(google_news.requests, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("network unavailable")))
    monkeypatch.setattr(google_news.time, "sleep", lambda seconds: None)
    with pytest.raises(RuntimeError, match="failed for every query"):
        google_news.fetch_events()


def test_normalize_link_removes_tracking_parameters():
    actual = google_news._normalize_link("https://EXAMPLE.com/story/?utm_source=news&ref=homepage&fbclid=abc#section")
    assert actual == "https://example.com/story?ref=homepage"


def test_duplicate_tracking_variants_merge(monkeypatch):
    entries = [entry("https://publisher.example/story?utm_source=google"), entry("https://publisher.example/story?utm_medium=rss")]
    patch_common(monkeypatch, entries)
    results = google_news.fetch_events()
    assert len(results) == 1
    assert len(results[0]["discovery_queries"]) == len(google_news.SEARCH_QUERIES)


def test_request_pacing_waits_between_feed_requests(monkeypatch):
    sleeps = []
    monkeypatch.setattr(google_news.requests, "get", lambda *a, **k: FakeResponse())
    monkeypatch.setattr(google_news.feedparser, "parse", lambda content: feed([]))
    monkeypatch.setattr(google_news.time, "sleep", lambda seconds: sleeps.append(seconds))
    google_news.fetch_events()
    assert sleeps.count(google_news.REQUEST_INTERVAL_SECONDS) == (
        len(google_news.SEARCH_QUERIES) * len(google_news.SEARCH_REGIONS) - 1
    )
