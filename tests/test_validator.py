
from datetime import date

from src.discovery.validator import validate_event


REFERENCE_DATE = date(2026, 11, 16)


def make_event(
    event_date="2026-12-20",
    city="Hyderabad",
    venue="",
):
    return {
        "artist": "Anuv Jain",
        "primary_date": event_date,
        "date_candidates": [],
        "city": city,
        "venue_candidate": venue,
        "source_text": "Anuv Jain live concert",
    }


def test_official_future_concert_is_confirmed():
    result = validate_event(
        event=make_event(),
        title="Anuv Jain live concert in Hyderabad",
        description="Tickets available for the concert.",
        source_name="Official promoter",
        source_url="https://example.com/event",
        source_is_official=True,
        reference_date=REFERENCE_DATE,
    )

    assert result["status"] == "confirmed"
    assert result["event_date"] == "2026-12-20"


def test_unverified_source_needs_review():
    result = validate_event(
        event=make_event(),
        title="Anuv Jain live concert in Hyderabad",
        description="Tickets available now.",
        source_is_official=False,
        reference_date=REFERENCE_DATE,
    )

    assert result["status"] == "needs_review"
    assert "not verified" in result["reason"]


def test_past_event_date_is_rejected():
    result = validate_event(
        event=make_event(event_date="2026-10-10"),
        title="Anuv Jain concert in Hyderabad",
        description="Anuv Jain performed live.",
        reference_date=REFERENCE_DATE,
    )

    assert result["status"] == "rejected"
    assert "past" in result["reason"]


def test_past_event_recap_is_rejected():
    result = validate_event(
        event=make_event(),
        title="Anuv Jain concert highlights from Hyderabad",
        description="Fans enjoyed the performance last night.",
        reference_date=REFERENCE_DATE,
    )

    assert result["status"] == "rejected"
    assert "past event" in result["reason"]


def test_missing_date_needs_review():
    result = validate_event(
        event=make_event(event_date=None),
        title="Anuv Jain announces a live concert",
        reference_date=REFERENCE_DATE,
    )

    assert result["status"] == "needs_review"
    assert "No valid event date" in result["reason"]


def test_missing_city_needs_review():
    result = validate_event(
        event=make_event(city=None),
        title="Anuv Jain live concert",
        description="Tickets available now.",
        source_is_official=True,
        reference_date=REFERENCE_DATE,
    )

    assert result["status"] == "needs_review"
    assert "city is missing" in result["reason"]


def test_unrelated_article_needs_review():
    result = validate_event(
        event=make_event(),
        title="Anuv Jain releases a new song",
        description="The singer talks about his music.",
        source_is_official=True,
        reference_date=REFERENCE_DATE,
    )

    assert result["status"] == "needs_review"
    assert "live-event announcement" in result["reason"]


def test_article_without_artist_mention_needs_review():
    result = validate_event(
        event=make_event(),
        title="Live concert announced in Hyderabad",
        description="Tickets are available now.",
        source_is_official=True,
        reference_date=REFERENCE_DATE,
    )

    assert result["status"] == "needs_review"
    assert "does not mention Anuv Jain" in result["reason"]