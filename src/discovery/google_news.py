"""Multi-query, multi-region Google News discovery for Anuv Jain."""

import logging
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

import feedparser
import requests

from src.config import ARTIST_NAME, REQUEST_TIMEOUT, is_relevant_event
from src.discovery.classifier import classify_event

logger = logging.getLogger(__name__)
GOOGLE_NEWS_URL = "https://news.google.com/rss/search"
USER_AGENT = "AnuvJainConcertAlerts/1.2"

# Be polite to Google News and recover from temporary throttling/network errors.
REQUEST_INTERVAL_SECONDS = 2.0
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 5.0
MAX_RETRY_DELAY_SECONDS = 30.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

SEARCH_QUERIES = (
    '"Anuv Jain" concert OR concerts',
    '"Anuv Jain" tour OR "tour dates"',
    '"Anuv Jain" tickets OR presale OR booking',
    '"Anuv Jain" live OR performance OR performing',
    '"Anuv Jain" festival OR lineup OR "music event"',
)

SEARCH_REGIONS = (
    {"name": "India", "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
    {"name": "United States", "hl": "en-US", "gl": "US", "ceid": "US:en"},
)


def _normalize_link(link: str) -> str:
    """Remove common tracking parameters for cross-query deduplication."""
    link = (link or "").strip()
    if not link:
        return ""
    parts = urlsplit(link)
    tracking = {"fbclid", "gclid", "mc_cid", "mc_eid"}
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in tracking and not key.lower().startswith("utm_")
    ]
    return urlunsplit((
        parts.scheme.lower(), parts.netloc.lower(),
        parts.path.rstrip("/") or "/", urlencode(query, doseq=True), "",
    ))


def _build_feed_url(query: str, region: dict) -> str:
    params = {
        "q": query, "hl": region["hl"],
        "gl": region["gl"], "ceid": region["ceid"],
    }
    return f"{GOOGLE_NEWS_URL}?{urlencode(params)}"


def _entry_source(entry: dict) -> str:
    source = entry.get("source", {})
    if isinstance(source, dict):
        return source.get("title", "Google News") or "Google News"
    return "Google News"


def _retry_delay(exc: Exception, attempt: int) -> float:
    """Use Retry-After when available; otherwise use bounded exponential backoff."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    retry_after = headers.get("Retry-After")
    if retry_after:
        try:
            return min(MAX_RETRY_DELAY_SECONDS, max(0.0, float(retry_after)))
        except (TypeError, ValueError):
            try:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return min(
                    MAX_RETRY_DELAY_SECONDS,
                    max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds()),
                )
            except (TypeError, ValueError, OverflowError):
                pass
    return min(MAX_RETRY_DELAY_SECONDS, RETRY_BACKOFF_SECONDS * (2 ** attempt))


def _get_feed_response(url: str, request_number: int):
    """Fetch one RSS feed with pacing and bounded retries."""
    if request_number > 0:
        time.sleep(REQUEST_INTERVAL_SECONDS)

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            return response
        except (requests.RequestException, OSError) as exc:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            retryable = status_code in RETRYABLE_STATUS_CODES or status_code is None
            if not retryable or attempt >= MAX_RETRIES:
                raise
            delay = _retry_delay(exc, attempt)
            logger.warning(
                "Temporary Google News request failure | attempt=%d/%d | "
                "status=%s | retry_in=%.1fs | error=%s",
                attempt + 1, MAX_RETRIES + 1, status_code, delay, exc,
            )
            time.sleep(delay)


def fetch_events() -> list[dict]:
    """Discover and classify articles; never confirms events or sends alerts."""
    discovered = {}
    successful_feeds = 0
    failed_feeds = []
    request_number = 0

    for region in SEARCH_REGIONS:
        for query in SEARCH_QUERIES:
            request_number += 1
            try:
                response = _get_feed_response(
                    _build_feed_url(query, region), request_number - 1
                )
                feed = feedparser.parse(response.content)
                if getattr(feed, "bozo", False) and not feed.entries:
                    raise RuntimeError(
                        "Unreadable RSS feed: "
                        f"{getattr(feed, 'bozo_exception', 'unknown parse error')}"
                    )
                successful_feeds += 1
            except Exception as exc:
                failed_feeds.append((region["name"], query, str(exc)))
                logger.warning(
                    "Search failed | region=%s | query=%s | error=%s",
                    region["name"], query, exc,
                )
                continue

            for entry in feed.entries:
                title = entry.get("title", "").strip()
                description = entry.get("summary", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue
                if not is_relevant_event(title, description):
                    continue

                normalized_link = _normalize_link(link)
                if not normalized_link:
                    continue

                if normalized_link in discovered:
                    existing = discovered[normalized_link]
                    if query not in existing["discovery_queries"]:
                        existing["discovery_queries"].append(query)
                    if region["name"] not in existing["discovery_regions"]:
                        existing["discovery_regions"].append(region["name"])
                    if len(description) > len(existing["description"]):
                        existing["description"] = description
                    continue

                classification = classify_event(title, description)
                discovered[normalized_link] = {
                    "id": normalized_link,
                    "artist": ARTIST_NAME,
                    "title": title,
                    "description": description,
                    "link": link,
                    "published": entry.get("published", ""),
                    "source": _entry_source(entry),
                    "status": classification["status"],
                    "reason": classification["reason"],
                    "discovery_query": query,
                    "discovery_region": region["name"],
                    "discovery_queries": [query],
                    "discovery_regions": [region["name"]],
                }

    if successful_feeds == 0:
        details = "; ".join(
            f"{region} / {query}: {error}"
            for region, query, error in failed_feeds[:3]
        )
        raise RuntimeError(
            "Google News discovery failed for every query and region. " + details
        )

    results = list(discovered.values())
    logger.info(
        "Google News discovery completed | feeds=%d/%d | articles=%d | failures=%d",
        successful_feeds, len(SEARCH_QUERIES) * len(SEARCH_REGIONS),
        len(results), len(failed_feeds),
    )
    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    results = fetch_events()
    print(f"Relevant articles discovered: {len(results)}")
    for event in results:
        print("\n--------------------------------------")
        print("Status:", event["status"])
        print("Title:", event["title"])
        print("Source:", event["source"])
        print("Published:", event["published"])
        print("Regions:", ", ".join(event["discovery_regions"]))
        print("Queries:", " | ".join(event["discovery_queries"]))
        print("Link:", event["link"])
