
import logging
from urllib.parse import urlencode

import feedparser
import requests

from src.config import (
    ARTIST_NAME,
    REQUEST_TIMEOUT,
    is_relevant_event,
)

from src.discovery.classifier import classify_event


logger = logging.getLogger(__name__)

GOOGLE_NEWS_URL = "https://news.google.com/rss/search"


def fetch_events() -> list[dict]:
    """
    Fetch Anuv Jain-related articles from Google News.

    Filters irrelevant articles, classifies potential events
    and returns structured results.
    """

    query = (
        '"Anuv Jain" '
        '(concert OR live OR tour OR fest OR tickets '
        'OR performance OR lineup OR announcement)'
    )

    params = {
        "q": query,
        "hl": "en-IN",
        "gl": "IN",
        "ceid": "IN:en",
    }

    url = f"{GOOGLE_NEWS_URL}?{urlencode(params)}"

    logger.info("Connecting to Google News RSS")

    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={
            "User-Agent": "AnuvJainConcertAlerts/1.0"
        },
    )

    response.raise_for_status()

    feed = feedparser.parse(response.content)

    if feed.bozo and not feed.entries:
        raise RuntimeError(
            f"Unable to parse Google News RSS: "
            f"{feed.bozo_exception}"
        )

    logger.info(
        "Google News articles retrieved: %d",
        len(feed.entries),
    )

    events = []
    seen_links = set()

    for entry in feed.entries:

        title = entry.get("title", "").strip()
        description = entry.get("summary", "").strip()
        link = entry.get("link", "").strip()

        # Required fields.
        if not title or not link:
            continue

        # Prevent duplicate articles within one fetch.
        if link in seen_links:
            continue

        seen_links.add(link)

        # Filter unrelated articles.
        if not is_relevant_event(title, description):
            continue

        # Classify the article.
        classification = classify_event(
            title=title,
            description=description,
        )

        source_info = entry.get("source", {})

        if not isinstance(source_info, dict):
            source_info = {}

        event = {
            "id": link,
            "artist": ARTIST_NAME,
            "title": title,
            "description": description,
            "link": link,
            "published": entry.get("published", ""),
            "source": source_info.get(
                "title",
                "Google News",
            ),
            "status": classification["status"],
            "reason": classification["reason"],
        }

        events.append(event)

    logger.info(
        "Relevant articles discovered: %d",
        len(events),
    )

    return events


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    try:
        results = fetch_events()

        print("\n========== DISCOVERY RESULTS ==========")

        print(f"Total relevant articles: {len(results)}")

        for event in results:

            print("\n--------------------------------------")

            print("Status:", event["status"])
            print("Title:", event["title"])
            print("Source:", event["source"])
            print("Published:", event["published"])
            print("Reason:", event["reason"])
            print("Link:", event["link"])

        print("\n========== CLASSIFICATION SUMMARY ==========")

        from collections import Counter

        summary = Counter(
            event["status"]
            for event in results
        )

        for status, count in summary.items():
            print(f"{status}: {count}")

    except requests.RequestException:
        logger.exception("Google News request failed")

    except Exception:
        logger.exception("Discovery engine failed")
