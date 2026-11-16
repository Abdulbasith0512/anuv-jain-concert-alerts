"""Explicit allowlist-based verification for official event sources."""

import os
from urllib.parse import urlparse


def _configured_domains() -> set[str]:
    raw = os.getenv("TRUSTED_EVENT_SOURCE_DOMAINS", "")
    return {
        item.strip().lower().rstrip(".")
        for item in raw.split(",")
        if item.strip()
    }


def is_trusted_event_source(article: dict) -> bool:
    """Trust only HTTPS URLs on explicitly allowlisted domains."""
    allowed = _configured_domains()
    if not allowed:
        return False
    url = article.get("publisher_url") or article.get("link") or ""
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            return False
        host = parsed.hostname.lower().rstrip(".")
    except (TypeError, ValueError):
        return False
    return any(host == domain or host.endswith("." + domain) for domain in allowed)
