import calendar
import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo


TIMEZONE = ZoneInfo("Asia/Kolkata")
MAX_FUTURE_YEARS = 3


# Canonical city names and common aliases.
CITIES = {
    # India
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
    "calcutta": "Kolkata",
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

    # International
    "atlanta": "Atlanta",
    "dubai": "Dubai",
    "abu dhabi": "Abu Dhabi",
    "singapore": "Singapore",
    "london": "London",
    "new york": "New York",
    "los angeles": "Los Angeles",
    "san francisco": "San Francisco",
    "chicago": "Chicago",
    "toronto": "Toronto",
    "vancouver": "Vancouver",
    "sydney": "Sydney",
    "melbourne": "Melbourne",
}


MONTHS = {
    month.lower(): index
    for index, month in enumerate(calendar.month_name)
    if month
}

MONTH_PATTERN = "|".join(
    sorted(MONTHS, key=len, reverse=True)
)


DATE_PATTERNS = [
    # 12 December 2026 / 12th December 2026
    re.compile(
        rf"\b(?P<day>\d{{1,2}})(?:st|nd|rd|th)?"
        rf"\s+(?P<month>{MONTH_PATTERN})"
        rf"(?:,?\s+(?P<year>20\d{{2}}))?\b",
        re.IGNORECASE,
    ),

    # December 12, 2026
    re.compile(
        rf"\b(?P<month>{MONTH_PATTERN})"
        rf"\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?"
        rf"(?:,?\s+(?P<year>20\d{{2}}))?\b",
        re.IGNORECASE,
    ),

    # 12/12/2026
    re.compile(
        r"\b(?P<day>\d{1,2})/(?P<month>\d{1,2})/"
        r"(?P<year>20\d{2})\b"
    ),
]


EVENT_CONTEXT = re.compile(
    r"\b("
    r"concert|show|gig|tour|perform(?:s|ed|ing)?|"
    r"performance|live|tickets?|presale|event|"
    r"scheduled|rescheduled|postponed|stage|"
    r"headline|setlist"
    r")\b",
    re.IGNORECASE,
)


PUBLICATION_CONTEXT = re.compile(
    r"\b("
    r"published|publication|updated|modified|posted|"
    r"uploaded|interview published|article published|"
    r"last updated|written by"
    r")\b",
    re.IGNORECASE,
)


RELATED_CONTENT_CONTEXT = re.compile(
    r"\b("
    r"read more|related articles|related stories|"
    r"you may also like|click here|more stories"
    r")\b",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """Decode HTML entities and normalize whitespace."""
    text = html.unescape(text or "")
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def extract_city(text: str) -> str | None:
    """Return the first recognized city in the supplied text."""
    normalized = normalize_text(text)

    for city in sorted(CITIES, key=len, reverse=True):
        pattern = rf"(?<!\w){re.escape(city)}(?!\w)"

        if re.search(pattern, normalized, re.IGNORECASE):
            return CITIES[city]

    return None


def _get_reference_date(
    reference_date: datetime | None,
) -> datetime:
    if reference_date is None:
        return datetime.now(TIMEZONE)

    if not isinstance(reference_date, datetime):
        raise TypeError(
            "reference_date must be a datetime object."
        )

    if reference_date.tzinfo is None:
        return reference_date.replace(tzinfo=TIMEZONE)

    return reference_date.astimezone(TIMEZONE)


def _sentence_bounds(
    text: str,
    position: int,
) -> tuple[int, int]:
    """Find the sentence containing a character position."""
    previous_boundaries = [
        match.end()
        for match in re.finditer(
            r"[.!?]\s+",
            text[:position],
        )
    ]

    start = (
        previous_boundaries[-1]
        if previous_boundaries
        else 0
    )

    next_boundary = re.search(
        r"[.!?]\s+",
        text[position:],
    )

    end = (
        position + next_boundary.start()
        if next_boundary
        else len(text)
    )

    return start, end


def _has_event_date_context(
    text: str,
    sentence_start: int,
    sentence_end: int,
    date_start: int,
) -> bool:
    """
    Require event context in the same sentence as the date.

    Publication dates are rejected when publication language
    appears before the date in that sentence.
    """
    sentence = text[sentence_start:sentence_end]

    prefix = text[
        max(sentence_start, date_start - 120):date_start
    ]

    if PUBLICATION_CONTEXT.search(prefix):
        return False

    if not EVENT_CONTEXT.search(sentence):
        return False

    if RELATED_CONTENT_CONTEXT.search(sentence):
        return False

    return True


def extract_dates(
    text: str,
    reference_date: datetime | None = None,
) -> list[dict]:
    """
    Extract explicit future event dates.

    Dates without a year are assigned to the next occurrence.
    Past dates and month-only references are not returned.

    Returned dates are candidates, not verified event dates.
    """
    text = normalize_text(text)

    if not text:
        return []

    reference = _get_reference_date(reference_date)

    matches = []

    for pattern in DATE_PATTERNS:
        matches.extend(pattern.finditer(text))

    matches.sort(key=lambda match: match.start())

    results = []
    seen_dates = set()

    for match in matches:
        sentence_start, sentence_end = _sentence_bounds(
            text,
            match.start(),
        )

        if not _has_event_date_context(
            text,
            sentence_start,
            sentence_end,
            match.start(),
        ):
            continue

        day = int(match.group("day"))
        month_text = match.group("month")
        year_text = match.group("year")

        if month_text.isdigit():
            month = int(month_text)
        else:
            month = MONTHS[month_text.lower()]

        year = (
            int(year_text)
            if year_text
            else reference.year
        )

        try:
            candidate = datetime(
                year,
                month,
                day,
                tzinfo=TIMEZONE,
            )
        except ValueError:
            continue

        # For a date without an explicit year, use the next
        # occurrence rather than silently choosing a past date.
        if (
            not year_text
            and candidate.date() < reference.date()
        ):
            try:
                candidate = candidate.replace(
                    year=year + 1
                )
            except ValueError:
                continue

        # Never return a past date as an upcoming candidate.
        if candidate.date() < reference.date():
            continue

        if candidate.year > reference.year + MAX_FUTURE_YEARS:
            continue

        date_value = candidate.date().isoformat()

        if date_value in seen_dates:
            continue

        seen_dates.add(date_value)

        results.append({
            "text": match.group(0),
            "date": date_value,
            "year": candidate.year,
            "month": candidate.month,
            "day": candidate.day,
        })

    return results


def _clean_venue_candidate(value: str) -> str | None:
    """Reject empty, generic, non-venue, or malformed candidates."""
    value = normalize_text(value).strip(" ,.-:;")
    # RSS fallback titles can append a publisher suffix to the venue.
    value = re.sub(r"\s+[-–—]\s+ARTS ATL$", "", value, flags=re.IGNORECASE)
    if not value or len(value) < 3:
        return None
    if value.lower() in {"the", "a", "an", "there", "here", "venue", "location", "stage"}:
        return None
    if re.search(r"&(?:nbsp|amp|quot|#\d+);", value, re.IGNORECASE):
        return None
    # Transport infrastructure is a frequent false match in tour/travel stories.
    if re.search(r"\b(?:airport|airfield|railway station|train station)\b", value, re.IGNORECASE):
        return None
    if re.search(r"\b(?:where|which|who|while|because|although)\b", value, re.IGNORECASE):
        return None
    # Normalize possessive city prefixes, e.g. Mumbai's Mehboob Studio.
    for city in sorted(CITIES, key=len, reverse=True):
        prefix = re.compile(rf"^{re.escape(city)}(?:['’]s)?\s+", re.IGNORECASE)
        value = prefix.sub("", value).strip(" ,.-")
    if value.lower() in CITIES:
        return None
    if re.fullmatch(r"\d{1,2}(:\d{2})?\s*(am|pm)?", value, re.IGNORECASE):
        return None
    return value[:70]


def extract_venue(text: str) -> str | None:
    """Extract a conservative venue candidate from an event-related sentence.

    The result is only a candidate and must never be treated as verified venue data.
    """
    text = normalize_text(text)
    if not text:
        return None

    sentences = re.split(r"(?<=[.!?])\s+", text)
    event_word = (
        r"concert|show|gig|tour|perform(?:s|ed|ing)?|performance|"
        r"live|playing|plays|event|stage"
    )
    pattern = re.compile(
        rf"\b(?:{event_word})\b.{{0,140}}?\bat\s+(?:the\s+)?"
        r"([A-Z][A-Za-z0-9&'’â€™(),. -]{2,70})",
        re.IGNORECASE,
    )

    clause_starts = re.compile(
        r",\s*(?:where|which|who|while|as|because|although|ahead\s+of|"
        r"with\s+the\s+show|and\s+the\s+show)\b",
        re.IGNORECASE,
    )
    stop_phrases = re.compile(
        r"\s+(?:in|on|for|tickets?|from|featuring|doors|after|before|during)\s+",
        re.IGNORECASE,
    )

    for sentence in sentences:
        sentence = sentence.strip()
        if RELATED_CONTENT_CONTEXT.search(sentence):
            continue
        match = pattern.search(sentence)
        if not match:
            continue

        venue = match.group(1).strip()
        # Cut explanatory clauses, but retain genuine comma-suffixed venue
        # areas such as "Jawaharlal Nehru Stadium, Pragati Vihar".
        clause = clause_starts.search(venue)
        if clause:
            venue = venue[:clause.start()].strip(" ,.-")

        # Trim trailing event metadata and city prepositions.
        stop = stop_phrases.search(venue)
        if stop:
            venue = venue[:stop.start()].strip(" ,.-")

        venue = _clean_venue_candidate(venue)
        if venue:
            return venue

    return None

def _extract_relevant_city(
    title: str,
    description: str,
) -> str | None:
    """
    Prefer a city in the headline.

    If absent, inspect article sentences containing the artist
    or event context. Ignore related-content snippets.
    """
    city = extract_city(title)

    if city:
        return city

    sentences = re.split(
        r"(?<=[.!?])\s+",
        normalize_text(description),
    )

    for sentence in sentences:
        if RELATED_CONTENT_CONTEXT.search(sentence):
            continue

        contains_artist = bool(
            re.search(
                r"\banuv\s+jain\b",
                sentence,
                re.IGNORECASE,
            )
        )

        contains_event_context = bool(
            EVENT_CONTEXT.search(sentence)
        )

        if not (contains_artist or contains_event_context):
            continue

        city = extract_city(sentence)

        if city:
            return city

    return None


def _is_editorial_headline(title: str) -> bool:
    """Identify interview/profile headlines that may discuss tours without announcing a concert."""
    patterns = (
        r"\binterview\b",
        r"\bin conversation\b",
        r"\bq\s*&\s*a\b",
        r"\bprofile\b",
        r"\bspeaks? (?:about|with|to)\b",
        r"\btalks? about\b",
        r"\bahead of (?:his|her|the) .{0,80}\b(?:tour|concert|show)\b",
        r"^my biggest audience\b",
    )
    return any(re.search(pattern, title, re.IGNORECASE) for pattern in patterns)


def _is_postponement_headline(title: str) -> bool:
    """Identify headlines where the old event details are no longer active."""
    return bool(re.search(
        r"\b(?:postpon(?:e|ed|es|ing)|reschedul(?:e|ed|es|ing)|postponement)\b",
        title,
        re.IGNORECASE,
    ))


def extract_event_details(
    title: str,
    description: str = "",
    reference_date: datetime | None = None,
) -> dict:
    title = normalize_text(title)
    description = normalize_text(description)

    combined_text = normalize_text(
        f"{title}. {description}"
    )

    # Editorial/interview headlines can discuss future tours without
    # announcing a specific concert. Do not inherit dates or venues from
    # unrelated article-body passages.
    editorial_headline = _is_editorial_headline(title)

    # A postponement headline describes a superseded event. Its old date
    # and venue are not active event details while a replacement is awaited.
    postponed_headline = _is_postponement_headline(title)

    suppress_body_event_details = editorial_headline or postponed_headline
    extraction_text = title if suppress_body_event_details else combined_text

    dates = (
        []
        if postponed_headline
        else extract_dates(
            extraction_text,
            reference_date=reference_date,
        )
    )

    city = _extract_relevant_city(
        title,
        description,
    )

    venue = extract_venue(extraction_text)

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
            dates[0]["date"]
            if dates
            else None
        ),
        "city": city,
        "venue_candidate": venue,
        "missing_fields": missing_fields,
        "extraction_complete": not missing_fields,
        "verification_status": "unverified",
        "source_text": combined_text,
    }
