
import json
import logging

import requests
from bs4 import BeautifulSoup
from googlenewsdecoder import gnewsdecoder

from src.config import REQUEST_TIMEOUT


logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _extract_jsonld_article(soup):
    """Find Article or NewsArticle structured data."""

    for script in soup.find_all(
        "script",
        type="application/ld+json",
    ):
        try:
            data = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue

        items = data if isinstance(data, list) else [data]

        index = 0

        while index < len(items):
            item = items[index]
            index += 1

            if not isinstance(item, dict):
                continue

            graph = item.get("@graph")

            if isinstance(graph, list):
                items.extend(
                    x for x in graph
                    if isinstance(x, dict)
                )

            article_type = item.get("@type", [])

            if isinstance(article_type, str):
                article_type = [article_type]

            if any(
                kind in (
                    "Article",
                    "NewsArticle",
                    "ReportageNewsArticle",
                )
                for kind in article_type
            ):
                return item

    return None


def _extract_meta_content(soup, selectors):
    """Return the first available metadata content value."""

    for attrs in selectors:
        tag = soup.find("meta", attrs=attrs)

        if tag and tag.get("content"):
            return tag["content"].strip()

    return None


def _extract_article_text(soup, jsonld):
    """Extract readable article text."""

    if jsonld:
        article_body = jsonld.get("articleBody")

        if isinstance(article_body, str) and article_body.strip():
            return article_body.strip()

    article = soup.find("article")

    if article:
        for element in article.select(
            "script, style, nav, footer, aside, form"
        ):
            element.decompose()

        text = article.get_text(" ", strip=True)

        if len(text) > 100:
            return text

    selectors = [
        "[itemprop='articleBody']",
        ".article__content",
        ".article-content",
        ".story-content",
        ".story__content",
        ".article-body",
        ".story-body",
        "main",
    ]

    for selector in selectors:
        element = soup.select_one(selector)

        if element:
            text = element.get_text(" ", strip=True)

            if len(text) > 100:
                return text

    return soup.get_text(" ", strip=True)[:15000]


def fetch_article_details(google_news_url: str) -> dict:
    """
    Resolve a Google News URL and retrieve publisher content.

    Extracted data is evidence, not independently verified.
    Publication and modification dates are kept separate.
    """

    result = {
        "google_news_url": google_news_url,
        "publisher_url": None,
        "title": None,
        "published": None,
        "modified": None,
        "article_text": "",
        "fetch_status": "failed",
        "error": None,
    }

    if not google_news_url:
        result["error"] = "Missing Google News URL."
        return result

    try:
        decoded = gnewsdecoder(
            google_news_url,
            interval=1,
            timeout=REQUEST_TIMEOUT,
        )

        if not decoded or not decoded.get("success"):
            result["error"] = (
                decoded.get(
                    "message",
                    "Google News URL decoding failed.",
                )
                if isinstance(decoded, dict)
                else "Invalid decoder response."
            )
            return result

        publisher_url = decoded.get("decoded_url")

        if not publisher_url:
            result["error"] = "No publisher URL returned."
            return result

        result["publisher_url"] = publisher_url

        response = requests.get(
            publisher_url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        jsonld = _extract_jsonld_article(soup)

        # Extract article title.
        title_tag = soup.find(
            "meta",
            property="og:title",
        )

        result["title"] = (
            title_tag.get("content")
            if title_tag and title_tag.get("content")
            else (
                soup.title.get_text(strip=True)
                if soup.title
                else None
            )
        )

        # Extract publication date from publisher metadata.
        published = _extract_meta_content(
            soup,
            [
                {"property": "article:published_time"},
                {"name": "pubdate"},
                {"name": "publishdate"},
                {"name": "date"},
                {"itemprop": "datePublished"},
            ],
        )

        if not published and jsonld:
            published = jsonld.get("datePublished")

        if not published:
            time_tag = soup.find(
                "time",
                attrs={"itemprop": "datePublished"},
            )

            if time_tag:
                published = time_tag.get("datetime")

        result["published"] = published

        # Extract modification date separately.
        modified = _extract_meta_content(
            soup,
            [
                {"property": "article:modified_time"},
                {"name": "last-modified"},
                {"itemprop": "dateModified"},
            ],
        )

        if not modified and jsonld:
            modified = jsonld.get("dateModified")

        if not modified:
            time_tag = soup.find(
                "time",
                attrs={"itemprop": "dateModified"},
            )

            if time_tag:
                modified = time_tag.get("datetime")

        result["modified"] = modified

        # Extract article body.
        result["article_text"] = _extract_article_text(
            soup,
            jsonld,
        )

        result["fetch_status"] = "success"

    except requests.RequestException as exc:
        result["error"] = f"Publisher request failed: {exc}"
        logger.warning(result["error"])

    except Exception as exc:
        result["error"] = str(exc)
        logger.exception("Article extraction failed")

    return result
