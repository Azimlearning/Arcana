"""Web page parser -- URL fetch + HTML text extraction (FR-ING-02).

Uses httpx for async HTTP and BeautifulSoup for content extraction.
Returns one PageText per logical ~1500-char section so chunk attribution
preserves meaningful section numbers for citation provenance.

Accepted content-types: text/html and text/plain.
Blocked URL schemes: file, javascript, data, ftp.
Max response body: 10 MB (prevents OOM on large pages).
"""

from __future__ import annotations

import re
from hashlib import sha256
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup  # type: ignore[import-untyped]

from api.core.errors import IngestFailed
from api.ingestion.types import PageText

_SECTION_TARGET_CHARS = 1500
_REQUEST_TIMEOUT = 15.0
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB
_USER_AGENT = "Arcana/1.0 (academic text extraction; research tool)"
_BLOCKED_SCHEMES = frozenset({"file", "javascript", "data", "ftp"})
_NOISE_TAGS = ["script", "style", "nav", "header", "footer", "aside",
               "noscript", "iframe", "svg", "figure", "button", "form"]
_BLOCK_TAGS = frozenset({"p", "h1", "h2", "h3", "h4", "h5", "h6",
                          "li", "blockquote", "td", "th", "pre"})
_MIN_FRAGMENT_LEN = 25


async def fetch_and_parse(url: str) -> tuple[str, list[PageText]]:
    """Fetch *url* and extract clean text.

    Returns (title, pages) where *pages* groups text into logical
    sections (~1500 chars each) for per-section citation attribution.

    Raises IngestFailed on network errors, HTTP errors, unsupported
    content-type, or empty extracted text.
    """
    _validate_url(url)

    try:
        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url, headers={"User-Agent": _USER_AGENT})
            resp.raise_for_status()
    except httpx.TimeoutException as exc:
        raise IngestFailed(f"URL fetch timed out after {_REQUEST_TIMEOUT}s: {url}") from exc
    except httpx.HTTPStatusError as exc:
        raise IngestFailed(
            f"HTTP {exc.response.status_code} fetching URL",
            details={"url": url, "status": exc.response.status_code},
        ) from exc
    except httpx.RequestError as exc:
        raise IngestFailed(f"Network error fetching {url}: {exc}") from exc

    ct = resp.headers.get("content-type", "").lower()
    if "html" not in ct and "text" not in ct:
        raise IngestFailed(
            f"Unsupported content-type {ct!r} -- only HTML and plain text are accepted.",
            details={"url": url, "content_type": ct},
        )

    raw_html = resp.content[:_MAX_RESPONSE_BYTES]
    soup = BeautifulSoup(raw_html, "html.parser")
    title = _extract_title(soup, url)
    text = _extract_text(soup)

    if not text.strip():
        raise IngestFailed(
            "No text content extracted from URL -- page may be JavaScript-rendered.",
            details={"url": url},
        )

    pages = _text_to_pages(text)
    return title, pages


def doc_id_for_url(url: str) -> str:
    """Stable, filesystem-safe doc_id derived from the URL."""
    digest = sha256(url.encode()).hexdigest()[:16]
    return f"url_{digest}"


# -- Internals -----------------------------------------------------------------


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if not parsed.scheme:
        raise IngestFailed(f"URL has no scheme: {url!r}")
    if parsed.scheme.lower() in _BLOCKED_SCHEMES:
        raise IngestFailed(f"Blocked URL scheme {parsed.scheme!r}")
    if not parsed.netloc:
        raise IngestFailed(f"URL has no host: {url!r}")


def _extract_title(soup: BeautifulSoup, fallback: str) -> str:
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):  # type: ignore[union-attr]
        return str(og["content"]).strip()[:256]  # type: ignore[index]
    title_tag = soup.find("title")
    if title_tag:
        return title_tag.get_text(strip=True)[:256]
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)[:256]
    return fallback[:128]


def _extract_text(soup: BeautifulSoup) -> str:
    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    # Prefer semantic containers; fall back to <body>.
    main = (
        soup.find("article")
        or soup.find("main")
        or soup.find("div", role="main")
        or soup.find("body")
        or soup
    )

    fragments: list[str] = []
    for el in main.descendants:  # type: ignore[union-attr]
        if getattr(el, "name", None) in _BLOCK_TAGS:
            text = el.get_text(separator=" ", strip=True)
            if len(text) >= _MIN_FRAGMENT_LEN:
                fragments.append(text)

    if not fragments:
        raw = main.get_text(separator="\n", strip=True)  # type: ignore[union-attr]
        fragments = [ln for ln in raw.splitlines() if len(ln.strip()) >= _MIN_FRAGMENT_LEN]

    # Deduplicate while preserving order (dict trick).
    return "\n\n".join(dict.fromkeys(fragments))


def _text_to_pages(text: str) -> list[PageText]:
    """Group paragraphs into logical sections of ~_SECTION_TARGET_CHARS chars."""
    paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    pages: list[PageText] = []
    bucket: list[str] = []
    bucket_len = 0

    for para in paras:
        bucket.append(para)
        bucket_len += len(para)
        if bucket_len >= _SECTION_TARGET_CHARS:
            pages.append(PageText(page=len(pages) + 1, text="\n\n".join(bucket)))
            bucket = []
            bucket_len = 0

    if bucket:
        pages.append(PageText(page=len(pages) + 1, text="\n\n".join(bucket)))

    return pages or [PageText(page=1, text=text)]
