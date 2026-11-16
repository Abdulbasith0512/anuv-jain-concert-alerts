
import logging
from datetime import date, datetime, time
from typing import Any, Callable

from src.discovery.google_news import fetch_events
from src.discovery.article_fetcher import fetch_article_details
from src.discovery.classifier import classify_event
from src.discovery.event_extractor import extract_event_details
from src.discovery.validator import validate_event
from src.discovery.source_verifier import is_trusted_event_source
from src.discovery.deduplicator import (
    compare_events,
    deduplicate_events,
)
from src.notifications.ntfy import send_notification
from src.storage.events import load_events, save_events


logger = logging.getLogger(__name__)


def _to_iso_date(value: Any) -> str | None:
    """Convert supported date representations into ISO format."""

    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, dict):
        value = value.get("date")

    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except ValueError:
            return None

    return None


def _json_safe(value: Any) -> Any:
    """Convert date objects and nested values into JSON-safe data."""

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]

    return value


def _enrich_article(
    article: dict[str, Any],
    article_fetcher: Callable,
) -> dict[str, Any]:
    """
    Retrieve publisher content and merge it with RSS evidence.

    A failed article fetch does not discard the original RSS article.
    Publisher content is evidence, not proof of official status.
    """

    enriched = dict(article)

    google_news_url = article.get("link", "")

    try:
        details = article_fetcher(google_news_url)

    except Exception:
        logger.exception(
            "Article enrichment failed for %s",
            google_news_url,
        )
        enriched["article_fetch_status"] = "failed"
        enriched["article_fetch_error"] = "Article fetcher raised an exception."
        return enriched

    if not isinstance(details, dict):
        enriched["article_fetch_status"] = "failed"
        enriched["article_fetch_error"] = "Invalid article fetcher response."
        return enriched

    enriched["article_fetch_status"] = details.get(
        "fetch_status",
        "failed",
    )
    enriched["publisher_url"] = details.get("publisher_url")
    enriched["publisher_title"] = details.get("title")
    enriched["publisher_published"] = details.get("published")
    enriched["publisher_modified"] = details.get("modified")
    enriched["article_fetch_error"] = details.get("error")

    if details.get("fetch_status") != "success":
        return enriched

    publisher_url = details.get("publisher_url")

    if publisher_url:
        enriched["link"] = publisher_url

    publisher_title = details.get("title")

    if publisher_title:
        enriched["title"] = publisher_title

    publisher_published = details.get("published")

    if publisher_published:
        enriched["published"] = publisher_published

    article_text = details.get("article_text", "")

    if article_text:
        rss_description = article.get("description", "")

        enriched["description"] = (
            f"{rss_description}\n\n{article_text}"
            if rss_description
            else article_text
        )

    # Reclassify using the publisher article as additional evidence.
    # A previously identified past recap cannot be promoted.
    original_status = article.get("status")

    if original_status == "past_or_recap":
        enriched["status"] = "past_or_recap"
        enriched["reason"] = article.get(
            "reason",
            "Original discovery classified this article as a past recap.",
        )
    else:
        classification = classify_event(
            title=enriched.get("title", ""),
            description=enriched.get("description", ""),
        )

        enriched["status"] = classification["status"]
        enriched["reason"] = classification["reason"]

    return enriched


def _build_event_record(
    article: dict[str, Any],
    details: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    """Combine article, extraction and validation data."""

    primary_date = _to_iso_date(
        details.get("primary_date")
    )

    event_id = article.get("id") or article.get("link")

    if not event_id:
        raise ValueError("Discovered article has no unique ID.")

    return {
        "id": event_id,
        "artist": details.get("artist", "Anuv Jain"),
        "title": article.get("title", ""),
        "description": article.get("description", ""),
        "link": article.get("link", ""),
        "google_news_url": article.get("id", ""),
        "publisher_url": article.get("publisher_url"),
        "published": article.get("published", ""),
        "publisher_modified": article.get("publisher_modified"),
        "article_fetch_status": article.get(
            "article_fetch_status",
            "not_attempted",
        ),
        "source": article.get("source", "Unknown"),
        "primary_date": primary_date,
        "event_date": validation.get("event_date"),
        "date_candidates": _json_safe(
            details.get("date_candidates", [])
        ),
        "city": details.get("city"),
        "venue_candidate": details.get("venue_candidate"),
        "missing_fields": details.get("missing_fields", []),
        "extraction_complete": details.get(
            "extraction_complete",
            False,
        ),
        "classification_status": article.get("status"),
        "status": validation.get("status", "needs_review"),
        "reason": validation.get("reason", ""),
        "verification_status": (
            "verified"
            if (
                validation.get("status") == "confirmed"
                and validation.get("source_is_official")
            )
            else "unverified"
        ),
        "source_is_official": bool(
            validation.get("source_is_official", False)
        ),
    }


def run_pipeline(
    *,
    reference_date: date | None = None,
    fetcher: Callable | None = None,
    notifier: Callable | None = None,
    source_verifier: Callable | None = None,
    article_fetcher: Callable | None = None,
) -> dict[str, Any]:
    """
    Discover, enrich, extract, validate, deduplicate and store events.

    Network-dependent components are injectable for testing.

    Sources are unverified by default. A source verifier must
    explicitly approve a source before an event can be confirmed.
    """

    if reference_date is None:
        reference_date = datetime.now().date()

    if isinstance(reference_date, datetime):
        reference_date = reference_date.date()

    reference_datetime = datetime.combine(
        reference_date,
        time.min,
    )

    fetch = fetcher or fetch_events
    notify = notifier or send_notification

    # Enrichment is opt-in at the pipeline level.
    # main() enables it for normal application execution.
    enrich = article_fetcher

    # Trust is opt-in through an explicit domain allowlist.
    # Tests may inject a verifier; production fails closed by default.
    verify_source = source_verifier or is_trusted_event_source

    logger.info("Starting Anuv Jain concert discovery pipeline.")

    articles = fetch()

    logger.info("Articles received: %d", len(articles))

    processed_events = []

    classification_counts = {
        "potential_upcoming": 0,
        "past_or_recap": 0,
        "needs_review": 0,
    }

    validation_counts = {
        "confirmed": 0,
        "needs_review": 0,
        "rejected": 0,
    }

    article_fetch_counts = {
        "success": 0,
        "failed": 0,
        "not_attempted": 0,
    }

    for original_article in articles:

        article = dict(original_article)

        # Retrieve publisher article when an article fetcher is supplied.
        if enrich is not None:
            article = _enrich_article(article, enrich)

        fetch_status = article.get(
            "article_fetch_status",
            "not_attempted",
        )

        if fetch_status not in article_fetch_counts:
            fetch_status = "failed"

        article_fetch_counts[fetch_status] += 1

        title = article.get("title", "")
        description = article.get("description", "")

        classification = article.get(
            "status",
            "needs_review",
        )

        if classification not in classification_counts:
            classification = "needs_review"

        classification_counts[classification] += 1

        details = extract_event_details(
            title=title,
            description=description,
            reference_date=reference_datetime,
        )

        # Only upcoming candidates may be checked for trusted-source status.
        # A verifier exception fails closed.
        is_official = False
        if classification == "potential_upcoming":
            try:
                is_official = bool(verify_source(article))
            except Exception:
                logger.exception(
                    "Source verification failed for %s",
                    article.get("link", ""),
                )

        validation = validate_event(
            event=details,
            title=title,
            description=description,
            source_name=article.get("source", ""),
            source_url=article.get(
                "publisher_url"
            ) or article.get("link", ""),
            source_is_official=is_official,
            reference_date=reference_date,
        )

        # Classification is a mandatory gate, not merely another signal.
        if classification == "past_or_recap":
            validation["status"] = "rejected"
            validation["reason"] = (
                "Article was classified as a past-event recap."
            )
        elif classification != "potential_upcoming":
            validation["status"] = "needs_review"
            validation["reason"] = (
                "Classifier did not establish upcoming-event evidence."
            )

        validation_counts[validation["status"]] += 1

        record = _build_event_record(
            article,
            details,
            validation,
        )

        processed_events.append(record)

    # Deduplicate discoveries within this run.
    deduplication = deduplicate_events(processed_events)

    unique_events = deduplication["unique_events"]

    # Compare against previously stored records.
    stored_events = load_events()

    existing_ids = {
        event.get("id")
        for event in stored_events
    }

    new_events = []
    duplicate_existing_count = 0

    for event in unique_events:

        if event["id"] in existing_ids:
            duplicate_existing_count += 1
            continue

        already_exists = any(
            compare_events(existing, event) == "duplicate"
            for existing in stored_events + new_events
        )

        if already_exists:
            duplicate_existing_count += 1
            continue

        new_events.append(event)

    # Save new records in one operation.
    if new_events:
        save_events(stored_events + new_events)

    # Only newly discovered, explicitly confirmed events notify.
    notifications_sent = 0

    for event in new_events:

        if event["status"] != "confirmed":
            continue

        message = (
            f"Artist: {event['artist']}\n"
            f"Date: {event['event_date']}\n"
            f"City: {event['city']}\n"
            f"Venue: {event['venue_candidate'] or 'Not specified'}\n\n"
            f"Source: {event['source']}\n"
            f"{event['link']}"
        )

        try:
            if notify(
                title="Anuv Jain concert discovered!",
                message=message,
                click_url=event["link"],
            ):
                notifications_sent += 1

        except Exception:
            logger.exception(
                "Notification failed for event %s",
                event["id"],
            )

    summary = {
        "articles_fetched": len(articles),
        "articles_processed": len(processed_events),
        "article_fetch": article_fetch_counts,
        "classification": classification_counts,
        "validation": validation_counts,
        "new_events": len(new_events),
        "duplicates_within_run": deduplication["duplicate_count"],
        "duplicates_already_stored": duplicate_existing_count,
        "venue_conflicts": deduplication["review_count"],
        "notifications_sent": notifications_sent,
        "total_stored_events": len(stored_events) + len(new_events),
    }

    logger.info("Pipeline completed: %s", summary)

    return summary


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    try:
        summary = run_pipeline(
            article_fetcher=fetch_article_details,
        )

        print("\n========== PIPELINE SUMMARY ==========")

        for key, value in summary.items():
            print(f"{key}: {value}")

        print("\n======================================")

    except Exception:
        logger.exception("Concert discovery pipeline failed")
        raise


if __name__ == "__main__":
    main()
