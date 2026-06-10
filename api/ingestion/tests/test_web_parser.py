"""Tests for the web parser (FR-ING-02).

Uses unittest.mock to patch httpx.AsyncClient so no real HTTP calls are made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.core.errors import IngestFailed
from api.ingestion.parsers.web import doc_id_for_url, fetch_and_parse

SAMPLE_HTML = b"""<!DOCTYPE html>
<html>
<head>
  <title>Test Article</title>
  <meta property="og:title" content="OG Title">
</head>
<body>
  <article>
    <h1>Main Heading</h1>
    <p>This is the first paragraph with enough content to be included in extraction results.</p>
    <p>Second paragraph also has enough length to pass the minimum fragment threshold check.</p>
    <nav>This nav content should be removed by the parser cleaning step.</nav>
    <p>Third paragraph content that rounds out the article body section properly.</p>
  </article>
  <footer>Footer content should be removed.</footer>
</body>
</html>"""


def _mock_response(content: bytes = SAMPLE_HTML, status: int = 200, ct: str = "text/html") -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.status_code = status
    resp.headers = {"content-type": ct}
    resp.raise_for_status = MagicMock()
    return resp


def _make_client(response: MagicMock) -> MagicMock:
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.mark.asyncio
async def test_fetch_and_parse_returns_title_and_pages():
    client = _make_client(_mock_response())
    with patch("api.ingestion.parsers.web.httpx.AsyncClient", return_value=client):
        title, pages = await fetch_and_parse("https://example.com/article")
    # og:title preferred
    assert title == "OG Title"
    assert len(pages) >= 1
    assert all(p.page >= 1 for p in pages)
    # nav + footer text should not appear
    combined = " ".join(p.text for p in pages).lower()
    assert "footer" not in combined
    assert "nav content" not in combined


@pytest.mark.asyncio
async def test_fetch_and_parse_uses_title_tag_fallback():
    html = b"<html><head><title>Page Title</title></head><body><p>" + b"x" * 100 + b"</p></body></html>"
    client = _make_client(_mock_response(content=html))
    with patch("api.ingestion.parsers.web.httpx.AsyncClient", return_value=client):
        title, _ = await fetch_and_parse("https://example.com")
    assert title == "Page Title"


@pytest.mark.asyncio
async def test_fetch_and_parse_sections_long_content():
    # Build content that will produce multiple sections
    para = "Word " * 200  # ~1000 chars each
    html = ("<html><body>" + "".join(f"<p>S{i}: {para}</p>" for i in range(8)) + "</body></html>").encode()
    client = _make_client(_mock_response(content=html))
    with patch("api.ingestion.parsers.web.httpx.AsyncClient", return_value=client):
        _, pages = await fetch_and_parse("https://example.com")
    assert len(pages) > 1


@pytest.mark.asyncio
async def test_fetch_and_parse_raises_on_http_error():
    import httpx as _httpx
    resp = _mock_response(status=404)
    resp.raise_for_status.side_effect = _httpx.HTTPStatusError(
        "404", request=MagicMock(), response=resp
    )
    client = _make_client(resp)
    with patch("api.ingestion.parsers.web.httpx.AsyncClient", return_value=client):
        with pytest.raises(IngestFailed, match="HTTP 404"):
            await fetch_and_parse("https://example.com/missing")


@pytest.mark.asyncio
async def test_fetch_and_parse_raises_on_timeout():
    import httpx as _httpx
    client = AsyncMock()
    client.get = AsyncMock(side_effect=_httpx.TimeoutException("timed out"))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch("api.ingestion.parsers.web.httpx.AsyncClient", return_value=client):
        with pytest.raises(IngestFailed, match="timed out"):
            await fetch_and_parse("https://slow.example.com")


@pytest.mark.asyncio
async def test_fetch_and_parse_raises_on_wrong_content_type():
    client = _make_client(_mock_response(ct="application/pdf"))
    with patch("api.ingestion.parsers.web.httpx.AsyncClient", return_value=client):
        with pytest.raises(IngestFailed, match="content-type"):
            await fetch_and_parse("https://example.com/file.pdf")


@pytest.mark.asyncio
async def test_fetch_and_parse_rejects_blocked_scheme():
    with pytest.raises(IngestFailed, match="scheme"):
        await fetch_and_parse("file:///etc/passwd")


@pytest.mark.asyncio
async def test_fetch_and_parse_rejects_schemeless_url():
    with pytest.raises(IngestFailed, match="scheme"):
        await fetch_and_parse("example.com/no-scheme")


def test_doc_id_for_url_is_stable():
    url = "https://example.com/paper"
    assert doc_id_for_url(url) == doc_id_for_url(url)
    assert doc_id_for_url(url).startswith("url_")
    assert len(doc_id_for_url(url)) <= 128


def test_doc_id_for_url_differs_for_different_urls():
    assert doc_id_for_url("https://a.com") != doc_id_for_url("https://b.com")
