from datetime import datetime
from zoneinfo import ZoneInfo

from src.discovery.event_extractor import (
    extract_city,
    extract_dates,
    extract_venue,
    extract_event_details,
)


REFERENCE_DATE = datetime(
    2026,
    11,
    16,
    tzinfo=ZoneInfo("Asia/Kolkata"),
)


# CITY EXTRACTION

def test_extract_hyderabad():
    assert extract_city(
        "Anuv Jain concert in Hyderabad"
    ) == "Hyderabad"


def test_extract_bengaluru_alias():
    assert extract_city(
        "Anuv Jain live in Bangalore"
    ) == "Bengaluru"


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


def test_headline_city_takes_priority_over_unrelated_city():
    result = extract_event_details(
        title="Hyderabad: Anuv Jain mesmerises Hyderabad crowd",
        description="Related articles: Chandigarh music festival.",
        reference_date=REFERENCE_DATE,
    )

    assert result["city"] == "Hyderabad"


def test_city_is_not_extracted_from_unrelated_description():
    result = extract_event_details(
        title="Anuv Jain announces a new tour",
        description="Read more about events in Chandigarh.",
        reference_date=REFERENCE_DATE,
    )

    assert result["city"] is None


def test_extract_international_cities():
    assert extract_city(
        "Anuv Jain live in Atlanta"
    ) == "Atlanta"

    assert extract_city(
        "Anuv Jain concert in Dubai"
    ) == "Dubai"


def test_calcutta_alias_maps_to_kolkata():
    assert extract_city(
        "Anuv Jain live in Calcutta"
    ) == "Kolkata"


def test_city_can_be_extracted_from_relevant_article_sentence():
    result = extract_event_details(
        title="Anuv Jain announces a Dastakhat tour",
        description=(
            "The concert will take place in Atlanta. "
            "Read more about Chandigarh music festivals."
        ),
        reference_date=REFERENCE_DATE,
    )

    assert result["city"] == "Atlanta"


def test_related_article_city_is_not_used_as_fallback():
    result = extract_event_details(
        title="Anuv Jain announces a new tour",
        description=(
            "Read more about concerts in Chandigarh."
        ),
        reference_date=REFERENCE_DATE,
    )

    assert result["city"] is None


# DATE EXTRACTION

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
    assert extract_dates(
        "",
        REFERENCE_DATE,
    ) == []


def test_rejects_implausible_future_date():
    dates = extract_dates(
        "Anuv Jain concert on 16 November 2036",
        REFERENCE_DATE,
    )

    assert dates == []


def test_does_not_use_publication_date_as_event_date():
    result = extract_event_details(
        title=(
            "Anuv Jain interview published "
            "on 16 November 2026"
        ),
        description=(
            "The article discusses his musical journey."
        ),
        reference_date=REFERENCE_DATE,
    )

    assert result["primary_date"] is None


def test_past_event_date_is_not_returned_as_upcoming_candidate():
    dates = extract_dates(
        "Anuv Jain concert on 21 August 2026",
        REFERENCE_DATE,
    )

    assert dates == []


def test_month_only_reference_does_not_create_exact_date():
    dates = extract_dates(
        "Anuv Jain will perform this February",
        REFERENCE_DATE,
    )

    assert dates == []


def test_publication_date_before_event_date_does_not_hide_event_date():
    dates = extract_dates(
        "Article published on 10 November 2026. "
        "Anuv Jain concert on 12 December 2026.",
        REFERENCE_DATE,
    )

    assert len(dates) == 1
    assert dates[0]["date"] == "2026-12-12"


# VENUE EXTRACTION

def test_extract_venue():
    venue = extract_venue(
        "Anuv Jain performs at Phoenix Arena in Hyderabad"
    )

    assert venue == "Phoenix Arena"


def test_does_not_extract_generic_related_article_venue():
    result = extract_event_details(
        title="Anuv Jain announces a new tour",
        description=(
            "Read more at Chandigarh Music Arena."
        ),
        reference_date=REFERENCE_DATE,
    )

    assert result["venue_candidate"] is None


def test_extract_venue_from_event_listing_headline():
    venue = extract_venue(
        "Anuv Jain Dastakhat Tour at Variety Playhouse"
    )

    assert venue is not None
    assert "Variety Playhouse" in venue


def test_html_entities_are_decoded_in_venue():
    venue = extract_venue(
        "Anuv Jain concert at Phoenix&nbsp;Arena"
    )

    assert venue == "Phoenix Arena"


def test_incomplete_html_venue_is_rejected():
    venue = extract_venue(
        "Anuv Jain concert at the&nbsp;"
    )

    assert venue is None


# COMPLETE EVENT EXTRACTION

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


def test_dubai_is_extracted_from_postponement_headline():
    result = extract_event_details(
        title=(
            "Anuv Jain postpones Dubai concert scheduled "
            "for April 12, new date awaited"
        ),
        reference_date=REFERENCE_DATE,
    )

    assert result["city"] == "Dubai"
    assert result["primary_date"] is None
    assert result["venue_candidate"] is None
    assert "date" in result["missing_fields"]
    assert "venue" in result["missing_fields"]


# LIVE-DISCOVERY REGRESSION TESTS

def test_venue_stops_before_explanatory_where_clause():
    venue = extract_venue(
        "Anuv Jain's show at Regency Ballroom, where the show is nearly sold out ahead of his tour."
    )
    assert venue == "Regency Ballroom"


def test_airport_is_not_extracted_as_a_concert_venue():
    venue = extract_venue(
        "Anuv Jain's tour show at Calcutta airport turned into a night of magic."
    )
    assert venue is None


def test_comma_suffixed_venue_area_is_preserved():
    venue = extract_venue(
        "Anuv Jain will perform at Jawaharlal Nehru Stadium, Pragati Vihar."
    )
    assert venue == "Jawaharlal Nehru Stadium, Pragati Vihar"


def test_interview_headline_does_not_inherit_body_date_or_venue():
    result = extract_event_details(
        title=(
            "My biggest audience is in Delhi: Anuv Jain ahead "
            "of his Dastakhat World Tour"
        ),
        description=(
            "The Dastakhat World Tour concert will take place "
            "on 16 January 2027 at Jawaharlal Nehru Stadium, Pragati Vihar."
        ),
        reference_date=REFERENCE_DATE,
    )

    assert result["city"] == "Delhi"
    assert result["primary_date"] is None
    assert result["venue_candidate"] is None
    assert "date" in result["missing_fields"]
    assert "venue" in result["missing_fields"]


def test_postponement_does_not_expose_superseded_date_or_venue():
    result = extract_event_details(
        title=(
            "Anuv Jain postpones Dubai concert scheduled "
            "for April 12, new date awaited"
        ),
        description=(
            "The concert was originally scheduled for 12 April 2027 "
            "at Dubai Millennium Amphitheatre."
        ),
        reference_date=REFERENCE_DATE,
    )

    assert result["city"] == "Dubai"
    assert result["primary_date"] is None
    assert result["venue_candidate"] is None


def test_publisher_suffix_is_removed_from_venue_candidate():
    venue = extract_venue(
        "Anuv Jain Dastakhat Tour at Variety Playhouse - ARTS ATL"
    )

    assert venue == "Variety Playhouse"
