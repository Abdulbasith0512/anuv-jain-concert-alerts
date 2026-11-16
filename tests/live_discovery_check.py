
import logging
from datetime import datetime

from src.discovery.google_news import fetch_events
from src.discovery.article_fetcher import fetch_article_details
from src.discovery.event_extractor import extract_event_details
from src.main import _enrich_article


logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s",
)


def main():
    reference_date=datetime.now().astimezone()

    print("\n========== LIVE DISCOVERY TEST ==========")
    print("Reference date:", reference_date)
    print("Mode: READ ONLY")
    print("Storage: DISABLED")
    print("Notifications: DISABLED")

    # Step 1: Discover articles.
    print("\n[1] Fetching Google News articles...")

    try:
        articles = fetch_events()
    except Exception as exc:
        print("Google News discovery failed:", exc)
        return

    print("Articles discovered:", len(articles))

    if not articles:
        print("No relevant articles found.")
        return

    # Limit publisher requests during the first live test.
    articles = articles[:10]

    print("\n[2] Fetching publisher articles...")
    print("Maximum publisher requests:", len(articles))

    results = []

    for index, article in enumerate(articles, start=1):
        print(f"\nProcessing article {index}/{len(articles)}")

        enriched = _enrich_article(
            article,
            fetch_article_details,
        )

        details = extract_event_details(
            title=enriched.get("title", ""),
            description=enriched.get("description", ""),
            reference_date=reference_date,
        )

        result = {
            "title": enriched.get("title"),
            "source": enriched.get("source"),
            "publisher_url": enriched.get("publisher_url"),
            "fetch_status": enriched.get("article_fetch_status"),
            "classification": enriched.get("status"),
            "city": details.get("city"),
            "event_date": details.get("primary_date"),
            "venue": details.get("venue_candidate"),
            "missing_fields": details.get("missing_fields"),
        }

        results.append(result)

        print("Title:", result["title"])
        print("Source:", result["source"])
        print("Publisher fetch:", result["fetch_status"])
        print("Classification:", result["classification"])
        print("City:", result["city"])
        print("Event date:", result["event_date"])
        print("Venue:", result["venue"])
        print("Missing fields:", result["missing_fields"])

        if result["publisher_url"]:
            print("Publisher URL:", result["publisher_url"])

    # Step 3: Summary.
    print("\n========== LIVE TEST SUMMARY ==========")

    successful = sum(
        item["fetch_status"] == "success"
        for item in results
    )

    failed = sum(
        item["fetch_status"] == "failed"
        for item in results
    )

    print("Articles tested:", len(results))
    print("Publisher fetch successful:", successful)
    print("Publisher fetch failed:", failed)

    for status in (
        "potential_upcoming",
        "past_or_recap",
        "needs_review",
    ):
        count = sum(
            item["classification"] == status
            for item in results
        )
        print(f"{status}: {count}")

    print("\nStorage modified: NO")
    print("Notifications sent: NO")
    print("\n========================================")


if __name__ == "__main__":
    main()
