
from unittest.mock import Mock, patch

from src.discovery.article_fetcher import (
    fetch_article_details,
    _extract_article_text,
    _extract_jsonld_article,
)

SAMPLE_URL = "https://news.google.com/rss/articles/test"


def test_failed_decoder_returns_error():
    with patch(
        "src.discovery.article_fetcher.gnewsdecoder",
        return_value={"success": False, "message": "Decode failed"},
    ):
        result = fetch_article_details(SAMPLE_URL)

    assert result["fetch_status"] == "failed"
    assert result["error"] == "Decode failed"


def test_successful_article_fetch():
    html = """
    <html>
      <head>
        <title>Sample concert article</title>
        <meta property="og:title" content="Sample concert article">
        <meta property="article:modified_time"
              content="2026-02-25T15:30:00">
      </head>
      <body>
        <article>
          <h1>Sample concert article</h1>
          <p>Anuv Jain performed in Bengaluru on February 23.</p>
          <p>This is additional article text for testing extraction.</p>
        </article>
      </body>
    </html>
    """

    mock_response = Mock()
    mock_response.text = html
    mock_response.raise_for_status.return_value = None
    mock_response.url = "https://example.com/article"

    with patch(
        "src.discovery.article_fetcher.gnewsdecoder",
        return_value={
            "success": True,
            "decoded_url": "https://example.com/article",
        },
    ), patch(
        "src.discovery.article_fetcher.requests.get",
        return_value=mock_response,
    ):
        result = fetch_article_details(SAMPLE_URL)

    assert result["fetch_status"] == "success"
    assert result["publisher_url"] == "https://example.com/article"
    assert result["title"] == "Sample concert article"
    assert "February 23" in result["article_text"]
    assert result["modified"] == "2026-02-25T15:30:00"


def test_jsonld_article_extraction():
    from bs4 import BeautifulSoup

    html = """
    <html>
      <script type="application/ld+json">
      {
        "@type": "NewsArticle",
        "headline": "Anuv Jain concert",
        "articleBody": "Anuv Jain performed in Bengaluru on February 23."
      }
      </script>
    </html>
    """

    soup = BeautifulSoup(html, "html.parser")
    article = _extract_jsonld_article(soup)

    assert article is not None
    assert article["headline"] == "Anuv Jain concert"


def test_article_text_uses_jsonld_body():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup("<html><body></body></html>", "html.parser")

    article_text = _extract_article_text(
        soup,
        {"articleBody": "Anuv Jain performed in Bengaluru."},
    )

    assert article_text == "Anuv Jain performed in Bengaluru."
