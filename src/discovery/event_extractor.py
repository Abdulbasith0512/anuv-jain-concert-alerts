
import re
import calendar
from datetime import datetime
from zoneinfo import ZoneInfo

import dateparser
from dateparser.search import search_dates


TIMEZONE = ZoneInfo("Asia/Kolkata")

INDIAN_CITIES = {
    "hyderabad": "Hyderabad",
    "vijayawada": "Vijayawada",
    "guntur": "Guntur",
    "visakhapatnam": "Visakhapatnam",
    "vizag": "Visakhapatnam",
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "chennai": "Chennai",
    "mumbai": "Mumbai",
    "delhi": "Delhi",
    "new delhi": "New Delhi",
    "pune": "Pune",
    "kolkata": "Kolkata",
    "ahmedabad": "Ahmedabad",
    "jaipur": "Jaipur",
    "lucknow": "Lucknow",
    "kochi": "Kochi",
    "cochin": "Kochi",
    "goa": "Goa",
    "indore": "Indore",
    "bhopal": "Bhopal",
    "nagpur": "Nagpur",
    "surat": "Surat",
    "chandigarh": "Chandigarh",
    "gurugram": "Gurugram",
    "gurgaon": "Gurugram",
    "noida": "Noida",
    "thiruvananthapuram": "Thiruvananthapuram",
    "trivandrum": "Thiruvananthapuram",
    "mysuru": "Mysuru",
    "mysore": "Mysuru",
    "coimbatore": "Coimbatore",
    "mangalore": "Mangaluru",
    "mangaluru": "Mangaluru",
    "amritsar": "Amritsar",
    "varanasi": "Varanasi",
    "ranchi": "Ranchi",
    "patna": "Patna",
    "bhubaneswar": "Bhubaneswar",
    "dehradun": "Dehradun",
}


def normalize_text(text: str) -> str:
    """Normalize whitespace in article text."""
    return re.sub(r"\s+", " ", text or "").strip()


def extract_city(text: str) -> str | None:
    """Extract a recognized Indian city from text."""

    normalized = normalize_text(text).lower()

    for city in sorted(
        INDIAN_CITIES,
        key=len,
        reverse=True,
    ):
        pattern = rf"(?<!\w){re.escape(city)}(?!\w)"

        if re.search(pattern, normalized):
            return INDIAN_CITIES[city]

    return None


def extract_dates(
    text: str,
    reference_date: datetime | None = None,
) -> list[dict]:
    """
    Extract dates from article text.

    Dates without an explicit year are interpreted
    as the next occurrence relative to reference_date.
    """

    text = normalize_text(text)

    if not text:
        return []

    if reference_date is None:
        reference_date = datetime.now(TIMEZONE)

    if reference_date.tzinfo is None:
        reference_date = reference_date.replace(
            tzinfo=TIMEZONE
        )

    results = []
    seen_dates = set()

    def add_date(parsed_date, matched_text):

        if parsed_date is None:
            return

        if parsed_date.tzinfo is None:
            parsed_date = parsed_date.replace(
                tzinfo=TIMEZONE
            )

        parsed_date = parsed_date.astimezone(TIMEZONE)

        date_value = parsed_date.date().isoformat()

        if date_value in seen_dates:
            return

        seen_dates.add(date_value)

        results.append({
            "text": matched_text,
            "date": date_value,
            "year": parsed_date.year,
            "month": parsed_date.month,
            "day": parsed_date.day,
        })

    # Handle dates such as 12 December or 12 December 2026.
    month_pattern = (
        r"January|February|March|April|May|June|"
        r"July|August|September|October|November|December"
    )

    day_month_pattern = (
        rf"\b(?P<day>\d{{1,2}})(?:st|nd|rd|th)?"
        rf"\s+(?P<month>{month_pattern})"
        rf"(?:,?\s+(?P<year>20\d{{2}}))?\b"
    )

    for match in re.finditer(
        day_month_pattern,
        text,
        re.IGNORECASE,
    ):
        day = int(match.group("day"))
        month_name = match.group("month")
        year_text = match.group("year")

        month = list(calendar.month_name).index(
            month_name.capitalize()
        )

        year = (
            int(year_text)
            if year_text
            else reference_date.year
        )

        try:
            parsed_date = datetime(
                year,
                month,
                day,
                tzinfo=TIMEZONE,
            )
        except ValueError:
            continue

        # If year is missing and date has passed,
        # use the next year's occurrence.
        if (
            not year_text
            and parsed_date.date() < reference_date.date()
        ):
            try:
                parsed_date = parsed_date.replace(
                    year=year + 1
                )
            except ValueError:
                continue

        add_date(parsed_date, match.group(0))

    # Handle other date formats, such as:
    # December 12, 2026 and 12/12/2026.
    settings = {
        "RELATIVE_BASE": reference_date,
        "TIMEZONE": "Asia/Kolkata",
        "TO_TIMEZONE": "Asia/Kolkata",
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future",
        "DATE_ORDER": "DMY",
        "STRICT_PARSING": True,
    }

    matches = search_dates(
        text,
        languages=["en"],
        settings=settings,
    )

    if matches:
        for matched_text, parsed_date in matches:
            add_date(parsed_date, matched_text)

    return results


def extract_venue(text: str) -> str | None:
    """
    Extract a possible venue name.

    This is a candidate, not a verified venue.
    """

    text = normalize_text(text)

    patterns = [
        r"\bvenue\s*:\s*([^.;\n]{3,70})",
        r"\bat\s+([A-Z][A-Za-z0-9&'’.,() -]{2,60})",
    ]

    stop_words = [
        " in ",
        " on ",
        " for ",
        " tickets ",
        " from ",
        " with ",
        " featuring ",
        " doors ",
    ]

    for pattern in patterns:

        match = re.search(pattern, text)

        if not match:
            continue

        venue = match.group(1).strip(" ,.-")
        lower_venue = venue.lower()

        for stop_word in stop_words:

            position = lower_venue.find(stop_word)

            if position != -1:
                venue = venue[:position].strip(" ,.-")
                lower_venue = venue.lower()

        if not venue:
            continue

        if re.fullmatch(
            r"\d{1,2}(:\d{2})?\s*(am|pm)?",
            venue,
            re.IGNORECASE,
        ):
            continue

        return venue[:70]

    return None


def extract_event_details(
    title: str,
    description: str = "",
    reference_date: datetime | None = None,
) -> dict:
    """
    Extract structured information from an article.

    Extracted details are not independently verified.
    """

    combined_text = normalize_text(
        f"{title}. {description}"
    )

    dates = extract_dates(
        combined_text,
        reference_date=reference_date,
    )

    city = extract_city(combined_text)

    venue = extract_venue(combined_text)

    missing_fields = []

    if not dates:
        missing_fields.append("date")

    if not city:
        missing_fields.append("city")

    if not venue:
        missing_fields.append("venue")

    return {
        "artist": "Anuv Jain",
        "title": title,
        "date_candidates": dates,
        "primary_date": (
            dates[0]["date"] if dates else None
        ),
        "city": city,
        "venue_candidate": venue,
        "missing_fields": missing_fields,
        "extraction_complete": not missing_fields,
        "verification_status": "unverified",
        "source_text": combined_text,
    }
