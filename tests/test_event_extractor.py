
from datetime import datetime
from zoneinfo import ZoneInfo

from src.discovery.event_extractor import (
    extract_city,
    extract_dates,
    extract_venue,
    extract_event_details,
)


REFERENCE_DATE = datetime(
    2026, 11, 16,
    tzinfo=ZoneInfo("Asia/Kolkata"),
)


def test_extract_hyderabad():
    assert extract_city(
        "Anuv Jain concert in Hyderabad"
    ) == "Hyderabad"


def test_extract_bengaluru_alias():
    assert extract_city(
        "Anuv Jain live in Bangalore"
    ) == "Bengaluru"


def test_extract_date_with_year():
    dates = extract_dates(
        "Concert on 12 December 2026",
        REFERENCE_DATE,
    )

    assert dates
    assert dates[0]["date"] == "2026-12-12"


def test_extract_date_without_year():
    dates = extract_dates(
        "Concert on 12 December",
        REFERENCE_DATE,
    )

    assert dates
    assert dates[0]["date"] == "2026-12-12"


def test_empty_text_has_no_dates():
    assert extract_dates("", REFERENCE_DATE) == []


def test_extract_venue():
    venue = extract_venue(
        "Anuv Jain performs at Phoenix Arena in Hyderabad"
    )

    assert venue == "Phoenix Arena"


def test_complete_event_extraction():
    result = extract_event_details(
        title="Anuv Jain announces Hyderabad concert",
        description=(
            "Live performance on 12 December 2026 "
            "at Phoenix Arena."
        ),
        reference_date=REFERENCE_DATE,
    )

    assert result["artist"] == "Anuv Jain"
    assert result["city"] == "Hyderabad"
    assert result["primary_date"] == "2026-12-12"
    assert result["venue_candidate"] == "Phoenix Arena"
    assert result["verification_status"] == "unverified"


def test_missing_details_are_reported():
    result = extract_event_details(
        title="Anuv Jain concert announcement",
        reference_date=REFERENCE_DATE,
    )

    assert result["primary_date"] is None
    assert result["city"] is None
    assert "date" in result["missing_fields"]
    assert "city" in result["missing_fields"]


def test_city_matching_is_case_insensitive():
    assert extract_city(
        "ANUV JAIN LIVE IN MUMBAI"
    ) == "Mumbai"


def test_no_false_city_match_inside_word():
    assert extract_city(
        "Anuv Jain performs in Hyderabad"
    ) == "Hyderabad"

    assert extract_city(
        "Anuv Jain performs in Hydrabadia"
    ) is None
