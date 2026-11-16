
from src.discovery.deduplicator import (
    compare_events,
    deduplicate_events,
    event_identity,
    normalize_text,
)


def make_event(
    artist="Anuv Jain",
    event_date="2026-12-20",
    city="Hyderabad",
    venue="",
):
    return {
        "artist": artist,
        "primary_date": event_date,
        "city": city,
        "venue_candidate": venue,
    }


def test_normalize_text():
    assert normalize_text("Anuv Jain — LIVE!") == "anuv jain live"


def test_event_identity():
    event = make_event()

    assert event_identity(event) == (
        "anuv jain",
        "2026 12 20",
        "hyderabad",
    )


def test_same_event_is_duplicate():
    first = make_event(venue="Gachibowli Stadium")
    second = make_event(venue="Gachibowli Stadium")

    assert compare_events(first, second) == "duplicate"


def test_venue_missing_on_one_record_is_duplicate():
    first = make_event(venue="Gachibowli Stadium")
    second = make_event()

    assert compare_events(first, second) == "duplicate"


def test_conflicting_venues_need_review():
    first = make_event(venue="Gachibowli Stadium")
    second = make_event(venue="Hitex Exhibition Centre")

    assert compare_events(first, second) == "review"


def test_different_dates_are_distinct():
    first = make_event(event_date="2026-12-20")
    second = make_event(event_date="2026-12-21")

    assert compare_events(first, second) == "distinct"


def test_different_cities_are_distinct():
    first = make_event(city="Hyderabad")
    second = make_event(city="Bengaluru")

    assert compare_events(first, second) == "distinct"


def test_different_artists_are_distinct():
    first = make_event(artist="Anuv Jain")
    second = make_event(artist="Another Artist")

    assert compare_events(first, second) == "distinct"


def test_missing_date_is_not_automatically_merged():
    first = make_event(event_date=None)
    second = make_event(event_date=None)

    assert compare_events(first, second) == "distinct"


def test_deduplicate_event_list():
    first = make_event(venue="Gachibowli Stadium")
    second = make_event(venue="Gachibowli Stadium")
    third = make_event(event_date="2026-12-21")

    result = deduplicate_events([first, second, third])

    assert result["input_count"] == 3
    assert result["unique_count"] == 2
    assert result["duplicate_count"] == 1
    assert result["review_count"] == 0


def test_conflicting_venues_are_not_silently_merged():
    first = make_event(venue="Gachibowli Stadium")
    second = make_event(venue="Hitex Exhibition Centre")

    result = deduplicate_events([first, second])

    assert result["unique_count"] == 2
    assert result["duplicate_count"] == 0
    assert result["review_count"] == 1


def test_missing_city_is_not_automatically_merged():
    first = make_event(city=None)
    second = make_event(city=None)

    assert compare_events(first, second) == "distinct"
