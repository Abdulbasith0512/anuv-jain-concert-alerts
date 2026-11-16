
import re
from datetime import date, datetime
from typing import Any


ARTIST_NAME = "Anuv Jain"

LIVE_EVENT_PATTERN = re.compile(
    r"\b(concert|live show|live performance|tour date|"
    r"performing live|will perform|to perform|"
    r"takes the stage|tickets|ticket sales|"
    r"live in concert|music festival)\b",
    re.IGNORECASE,
)

PAST_EVENT_PATTERN = re.compile(
    r"\b(recap|highlights from|photos from|"
    r"performed at|performed in|took place|"
    r"was held|wrapped up|concluded|"
    r"last night|yesterday's concert|"
    r"fans attended|crowd enjoyed)\b",
    re.IGNORECASE,
)


def _parse_event_date(event: dict[str, Any]) -> date | None:
    raw_date = event.get("primary_date")

    if not raw_date:
        candidates = event.get("date_candidates", [])
        if candidates:
            raw_date = candidates[0].get("date")

    if isinstance(raw_date, datetime):
        return raw_date.date()

    if isinstance(raw_date, date):
        return raw_date

    if isinstance(raw_date, str):
        try:
            return date.fromisoformat(raw_date)
        except ValueError:
            return None

    return None


def validate_event(
    event: dict[str, Any],
    title: str = "",
    description: str = "",
    source_name: str = "",
    source_url: str = "",
    source_is_official: bool = False,
    reference_date: date | None = None,
) -> dict[str, Any]:

    if reference_date is None:
        reference_date = date.today()

    if isinstance(reference_date, datetime):
        reference_date = reference_date.date()

    # Only use actual article fields for evidence.
    article_text = f"{title or ''} {description or ''}".strip()

    result = {
        "status": "needs_review",
        "reason": "",
        "event_date": None,
        "city": event.get("city"),
        "venue": event.get("venue_candidate"),
        "source_name": source_name or None,
        "source_url": source_url or None,
        "source_is_official": bool(source_is_official),
    }

    event_date = _parse_event_date(event)

    result["event_date"] = (
        event_date.isoformat() if event_date else None
    )

    # 1. The article itself must mention the artist.
    if not re.search(
        rf"\b{re.escape(ARTIST_NAME)}\b",
        article_text,
        re.IGNORECASE,
    ):
        result["reason"] = "The article text does not mention Anuv Jain."
        return result

    # 2. Reject clear past-event reporting.
    if PAST_EVENT_PATTERN.search(article_text):
        result["status"] = "rejected"
        result["reason"] = (
            "Article appears to describe a past event or recap."
        )
        return result

    # 3. A valid event date is required.
    if event_date is None:
        result["reason"] = "No valid event date could be extracted."
        return result

    # 4. Reject dates before the reference date.
    if event_date < reference_date:
        result["status"] = "rejected"
        result["reason"] = "The extracted event date is in the past."
        return result

    # 5. The article itself must contain live-event evidence.
    if not LIVE_EVENT_PATTERN.search(article_text):
        result["reason"] = (
            "No clear live-event announcement language found."
        )
        return result

    # 6. A city is required for an actionable alert.
    if not event.get("city"):
        result["reason"] = (
            "Potential concert found, but the city is missing."
        )
        return result

    # 7. Official source verification is explicit.
    if not source_is_official:
        result["reason"] = (
            "Potential upcoming concert, but the source is not "
            "verified as official."
        )
        return result

    result["status"] = "confirmed"
    result["reason"] = (
        "Future live event with a date and city, reported by a "
        "verified official source."
    )

    return result
