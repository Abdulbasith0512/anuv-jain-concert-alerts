
from datetime import date

from src import main


def make_article(
    article_id="article-1",
    status="potential_upcoming",
):
    return {
        "id": article_id,
        "artist": "Anuv Jain",
        "title": "Anuv Jain announces concert in Hyderabad on 20 December 2026",
        "description": "Anuv Jain will perform live in Hyderabad on 20 December 2026.",
        "link": f"https://example.com/{article_id}",
        "published": "2026-11-16",
        "source": "Example News",
        "status": status,
        "reason": "Upcoming event language found",
    }


def make_details():
    return {
        "artist": "Anuv Jain",
        "title": "Anuv Jain concert",
        "primary_date": date(2026, 12, 20),
        "date_candidates": [
            {
                "date": date(2026, 12, 20),
                "text": "20 December 2026",
            }
        ],
        "city": "Hyderabad",
        "venue_candidate": "Example Arena",
        "missing_fields": [],
        "extraction_complete": True,
    }


def make_validation(status="needs_review"):
    return {
        "status": status,
        "reason": "Test validation",
        "event_date": "2026-12-20",
        "city": "Hyderabad",
        "venue": "Example Arena",
        "source_name": "Example News",
        "source_url": "https://example.com/article",
        "source_is_official": status == "confirmed",
    }


# --------------------------------------------------
# EXISTING PIPELINE TESTS
# --------------------------------------------------

def test_pipeline_stores_new_event(monkeypatch, tmp_path):
    events_file = tmp_path / "events.json"

    monkeypatch.setattr(main, "load_events", lambda: [])
    monkeypatch.setattr(
        main,
        "save_events",
        lambda events: events_file.write_text(
            __import__("json").dumps(events),
            encoding="utf-8",
        ),
    )
    monkeypatch.setattr(
        main,
        "extract_event_details",
        lambda **kwargs: make_details(),
    )
    monkeypatch.setattr(
        main,
        "validate_event",
        lambda **kwargs: make_validation(),
    )

    result = main.run_pipeline(
        reference_date=date(2026, 11, 16),
        fetcher=lambda: [make_article()],
        notifier=lambda **kwargs: True,
    )

    assert result["articles_fetched"] == 1
    assert result["new_events"] == 1
    assert result["notifications_sent"] == 0
    assert events_file.exists()


def test_unverified_source_never_sends_notification(monkeypatch):
    saved = []
    notifications = []

    monkeypatch.setattr(main, "load_events", lambda: [])
    monkeypatch.setattr(main, "save_events", saved.extend)
    monkeypatch.setattr(
        main,
        "extract_event_details",
        lambda **kwargs: make_details(),
    )
    monkeypatch.setattr(
        main,
        "validate_event",
        lambda **kwargs: make_validation("needs_review"),
    )

    result = main.run_pipeline(
        reference_date=date(2026, 11, 16),
        fetcher=lambda: [make_article()],
        notifier=lambda **kwargs: notifications.append(kwargs) or True,
    )

    assert len(saved) == 1
    assert len(notifications) == 0
    assert result["notifications_sent"] == 0


def test_confirmed_event_sends_notification(monkeypatch):
    saved = []
    notifications = []

    monkeypatch.setattr(main, "load_events", lambda: [])
    monkeypatch.setattr(main, "save_events", saved.extend)
    monkeypatch.setattr(
        main,
        "extract_event_details",
        lambda **kwargs: make_details(),
    )
    monkeypatch.setattr(
        main,
        "validate_event",
        lambda **kwargs: make_validation("confirmed"),
    )

    result = main.run_pipeline(
        reference_date=date(2026, 11, 16),
        fetcher=lambda: [make_article()],
        notifier=lambda **kwargs: notifications.append(kwargs) or True,
        source_verifier=lambda article: True,
    )

    assert len(saved) == 1
    assert len(notifications) == 1
    assert result["notifications_sent"] == 1


def test_existing_event_is_not_saved_or_notified(monkeypatch):
    existing = {
        "id": "article-1",
        "artist": "Anuv Jain",
        "primary_date": "2026-12-20",
        "city": "Hyderabad",
        "venue_candidate": "Example Arena",
    }

    save_calls = []
    notification_calls = []

    monkeypatch.setattr(main, "load_events", lambda: [existing])
    monkeypatch.setattr(main, "save_events", save_calls.append)
    monkeypatch.setattr(
        main,
        "extract_event_details",
        lambda **kwargs: make_details(),
    )
    monkeypatch.setattr(
        main,
        "validate_event",
        lambda **kwargs: make_validation("confirmed"),
    )

    result = main.run_pipeline(
        reference_date=date(2026, 11, 16),
        fetcher=lambda: [make_article()],
        notifier=lambda **kwargs: notification_calls.append(kwargs) or True,
        source_verifier=lambda article: True,
    )

    assert result["new_events"] == 0
    assert result["duplicates_already_stored"] == 1
    assert save_calls == []
    assert notification_calls == []


def test_past_recap_is_rejected(monkeypatch):
    saved = []

    monkeypatch.setattr(main, "load_events", lambda: [])
    monkeypatch.setattr(main, "save_events", saved.extend)
    monkeypatch.setattr(
        main,
        "extract_event_details",
        lambda **kwargs: make_details(),
    )
    monkeypatch.setattr(
        main,
        "validate_event",
        lambda **kwargs: make_validation("needs_review"),
    )

    result = main.run_pipeline(
        reference_date=date(2026, 11, 16),
        fetcher=lambda: [
            make_article(status="past_or_recap")
        ],
        notifier=lambda **kwargs: True,
    )

    assert result["validation"]["rejected"] == 1
    assert saved[0]["status"] == "rejected"


# --------------------------------------------------
# NEW PUBLISHER ARTICLE INTEGRATION TESTS
# --------------------------------------------------

def test_publisher_article_enriches_rss_article():
    article = make_article()

    def fake_article_fetcher(url):
        assert url == article["link"]

        return {
            "fetch_status": "success",
            "publisher_url": "https://publisher.example.com/concert",
            "title": "Anuv Jain concert announcement",
            "published": "2026-11-15",
            "modified": "2026-11-16",
            "article_text": (
                "Anuv Jain announces a new concert in Hyderabad "
                "scheduled for 20 December 2026."
            ),
            "error": None,
        }

    enriched = main._enrich_article(
        article,
        fake_article_fetcher,
    )

    assert enriched["article_fetch_status"] == "success"
    assert enriched["publisher_url"] == (
        "https://publisher.example.com/concert"
    )
    assert enriched["title"] == "Anuv Jain concert announcement"
    assert "20 December 2026" in enriched["description"]
    assert enriched["publisher_modified"] == "2026-11-16"
    assert enriched["id"] == article["id"]


def test_failed_publisher_fetch_preserves_rss_article():
    article = make_article()

    def failed_fetcher(url):
        return {
            "fetch_status": "failed",
            "publisher_url": None,
            "title": None,
            "published": None,
            "modified": None,
            "article_text": "",
            "error": "Publisher unavailable",
        }

    enriched = main._enrich_article(
        article,
        failed_fetcher,
    )

    assert enriched["article_fetch_status"] == "failed"
    assert enriched["title"] == article["title"]
    assert enriched["description"] == article["description"]
    assert enriched["id"] == article["id"]
    assert enriched["link"] == article["link"]


def test_past_publisher_article_is_classified_as_recap():
    article = make_article()

    def fake_article_fetcher(url):
        return {
            "fetch_status": "success",
            "publisher_url": "https://publisher.example.com/recap",
            "title": "Anuv Jain concludes Bengaluru concert",
            "published": "2026-02-25",
            "modified": "2026-02-26",
            "article_text": (
                "Anuv Jain performed in Bengaluru on February 23, 2026. "
                "The concert concluded after a successful performance."
            ),
            "error": None,
        }

    enriched = main._enrich_article(
        article,
        fake_article_fetcher,
    )

    assert enriched["status"] == "past_or_recap"


def test_publisher_modification_date_is_not_event_date():
    article = make_article()

    def fake_article_fetcher(url):
        return {
            "fetch_status": "success",
            "publisher_url": "https://publisher.example.com/concert",
            "title": "Anuv Jain concert announcement",
            "published": None,
            "modified": "2026-11-16",
            "article_text": (
                "Anuv Jain will perform in Hyderabad on 20 December 2026."
            ),
            "error": None,
        }

    enriched = main._enrich_article(
        article,
        fake_article_fetcher,
    )

    assert enriched["publisher_modified"] == "2026-11-16"
    assert enriched["publisher_published"] is None
    assert "20 December 2026" in enriched["description"]
