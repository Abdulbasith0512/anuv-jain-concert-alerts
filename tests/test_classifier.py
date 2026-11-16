
from src.discovery.classifier import classify_event


def test_upcoming_concert_announcement():
    result = classify_event(
        "Anuv Jain announces upcoming Hyderabad concert"
    )
    assert result["status"] == "potential_upcoming"


def test_past_performance():
    result = classify_event(
        "Anuv Jain performed in Hyderabad last night"
    )
    assert result["status"] == "past_or_recap"


def test_song_release_needs_review():
    result = classify_event(
        "Anuv Jain releases a new song"
    )
    assert result["status"] == "needs_review"


def test_ticket_announcement():
    result = classify_event(
        "Anuv Jain tickets are on sale"
    )
    assert result["status"] == "potential_upcoming"


def test_past_event_recap():
    result = classify_event(
        "Anuv Jain concert recap: performed last night"
    )
    assert result["status"] == "past_or_recap"


def test_description_is_considered():
    result = classify_event(
        "Anuv Jain announces a special event",
        "The singer will perform live in Mumbai."
    )
    assert result["status"] == "potential_upcoming"


def test_empty_article_needs_review():
    result = classify_event("")
    assert result["status"] == "needs_review"