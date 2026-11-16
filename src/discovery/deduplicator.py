
import re
import unicodedata
from typing import Any


def normalize_text(value: Any) -> str:
    """Normalize text for reliable event comparisons."""
    if not value:
        return ""

    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def event_identity(event: dict[str, Any]) -> tuple[str, str, str] | None:
    """
    Generate a conservative identity key.

    Events without an artist, date, or city cannot be
    automatically deduplicated.
    """
    artist = normalize_text(event.get("artist"))
    event_date = normalize_text(
        event.get("primary_date") or event.get("event_date")
    )
    city = normalize_text(event.get("city"))

    if not artist or not event_date or not city:
        return None

    return artist, event_date, city


def compare_events(
    first: dict[str, Any],
    second: dict[str, Any],
) -> str:
    """
    Compare two event records.

    Returns:
        duplicate: Same artist, date, city, and compatible venue.
        review: Same core event identity but venue information conflicts.
        distinct: Different or insufficient event identity.
    """
    first_identity = event_identity(first)
    second_identity = event_identity(second)

    if first_identity is None or second_identity is None:
        return "distinct"

    if first_identity != second_identity:
        return "distinct"

    first_venue = normalize_text(
        first.get("venue") or first.get("venue_candidate")
    )
    second_venue = normalize_text(
        second.get("venue") or second.get("venue_candidate")
    )

    # Conflicting venue information needs human review.
    if first_venue and second_venue and first_venue != second_venue:
        return "review"

    return "duplicate"


def deduplicate_events(
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Remove confidently identified duplicates.

    Conflicting venue records are kept separate and flagged
    for review instead of being silently merged.
    """
    unique_events = []
    duplicates = []
    review_pairs = []

    for event in events:
        matched_duplicate = False

        for existing in unique_events:
            comparison = compare_events(existing, event)

            if comparison == "duplicate":
                duplicates.append({
                    "event": event,
                    "duplicate_of": existing,
                })
                matched_duplicate = True
                break

            if comparison == "review":
                review_pairs.append({
                    "first": existing,
                    "second": event,
                    "reason": "Conflicting venue information",
                })

        if not matched_duplicate:
            unique_events.append(event)

    return {
        "unique_events": unique_events,
        "duplicates": duplicates,
        "review_pairs": review_pairs,
        "input_count": len(events),
        "unique_count": len(unique_events),
        "duplicate_count": len(duplicates),
        "review_count": len(review_pairs),
    }
