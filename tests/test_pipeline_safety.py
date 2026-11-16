from datetime import date

from src import main


def test_needs_review_article_cannot_be_confirmed_even_if_verifier_approves(monkeypatch):
    saved = []
    notifications = []

    article = {
        "id": "needs-review-article",
        "artist": "Anuv Jain",
        "title": "Anuv Jain interview",
        "description": "Anuv Jain discusses music.",
        "link": "https://publisher.example/interview",
        "published": "2026-11-16",
        "source": "Example News",
        "status": "needs_review",
        "reason": "No upcoming event evidence",
    }
    details = {
        "artist": "Anuv Jain",
        "primary_date": date(2026, 12, 20),
        "date_candidates": [{"date": date(2026, 12, 20)}],
        "city": "Hyderabad",
        "venue_candidate": "Example Arena",
        "missing_fields": [],
        "extraction_complete": True,
    }

    monkeypatch.setattr(main, "load_events", lambda: [])
    monkeypatch.setattr(main, "save_events", saved.extend)
    monkeypatch.setattr(main, "extract_event_details", lambda **kwargs: details)
    monkeypatch.setattr(
        main,
        "validate_event",
        lambda **kwargs: {
            "status": "confirmed",
            "reason": "Mock validator accepted it",
            "event_date": "2026-12-20",
            "city": "Hyderabad",
            "venue": "Example Arena",
            "source_name": "Example News",
            "source_url": "https://publisher.example/interview",
            "source_is_official": True,
        },
    )

    result = main.run_pipeline(
        reference_date=date(2026, 11, 16),
        fetcher=lambda: [article],
        notifier=lambda **kwargs: notifications.append(kwargs) or True,
        source_verifier=lambda article: True,
    )

    assert result["validation"]["needs_review"] == 1
    assert saved[0]["status"] == "needs_review"
    assert saved[0]["verification_status"] == "unverified"
    assert notifications == []
