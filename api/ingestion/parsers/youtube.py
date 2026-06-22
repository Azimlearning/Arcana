"""YouTube transcript parser — video URL → transcript text (FR-ING-03).

Mirrors ``parsers/web.py``: returns ``(title, pages)`` where *pages* group
the transcript into ~1500-char logical sections so chunk attribution
preserves section provenance for citations. The transcript is fetched via
``youtube-transcript-api`` (network, sync — run off the event loop); the
title comes from YouTube's public oEmbed endpoint (no API key required).

Accepted URL forms:
    https://www.youtube.com/watch?v=<id>
    https://youtu.be/<id>
    https://www.youtube.com/embed/<id> | /shorts/<id> | /v/<id>
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import parse_qs, urlparse

import httpx

from api.core.errors import IngestFailed
from api.ingestion.types import PageText

_SECTION_TARGET_CHARS = 1500
_OEMBED_URL = "https://www.youtube.com/oembed"
_REQUEST_TIMEOUT = 15.0


async def fetch_and_parse(url: str) -> tuple[str, list[PageText]]:
    """Fetch *url*'s transcript and group it into sections.

    Raises IngestFailed on an unrecognised URL, a missing/disabled
    transcript, or empty transcript text.
    """
    video_id = extract_video_id(url)
    segments = await asyncio.to_thread(_fetch_transcript, video_id)
    if not segments:
        raise IngestFailed(
            "No transcript available for this video (captions may be disabled).",
            details={"url": url, "video_id": video_id},
        )

    text = " ".join(
        seg.get("text", "").strip() for seg in segments if seg.get("text", "").strip()
    )
    if not text.strip():
        raise IngestFailed("Transcript was empty.", details={"url": url})

    title = await _fetch_title(url, fallback=f"YouTube video {video_id}")
    pages = _text_to_pages(text)
    return title, pages


def doc_id_for_url(url: str) -> str:
    """Stable, filesystem-safe doc_id derived from the video id."""
    return f"yt_{extract_video_id(url)}"


def extract_video_id(url: str) -> str:
    """Pull the 11-char video id out of common YouTube URL shapes."""
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()

    if "youtu.be" in host:
        vid = parsed.path.lstrip("/").split("/")[0]
        if vid:
            return vid
    elif "youtube.com" in host:
        if parsed.path == "/watch":
            qs = parse_qs(parsed.query)
            if qs.get("v"):
                return qs["v"][0]
        m = re.match(r"^/(?:embed|shorts|v)/([^/?#]+)", parsed.path)
        if m:
            return m.group(1)

    raise IngestFailed(f"Not a recognised YouTube video URL: {url!r}")


# -- Internals -----------------------------------------------------------------


def _fetch_transcript(video_id: str) -> list[dict]:
    """Fetch transcript segments as ``[{"text": ...}, ...]``.

    Tolerates both the 1.x instance API (``.fetch()``) and the legacy
    classmethod (``get_transcript``). Lives behind one seam so tests can
    monkeypatch it without the package installed.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - dep guard
        raise IngestFailed(
            "youtube-transcript-api is not installed; cannot ingest YouTube URLs."
        ) from exc

    try:
        api = YouTubeTranscriptApi()
        if hasattr(api, "fetch"):
            fetched = api.fetch(video_id)
            return [{"text": getattr(s, "text", "")} for s in fetched]
        return YouTubeTranscriptApi.get_transcript(video_id)  # type: ignore[attr-defined]
    except IngestFailed:
        raise
    except Exception as exc:  # normalise any library error into IngestFailed
        raise IngestFailed(
            f"Could not fetch transcript: {exc}", details={"video_id": video_id}
        ) from exc


async def _fetch_title(url: str, *, fallback: str) -> str:
    """Best-effort video title via YouTube oEmbed; falls back silently."""
    try:
        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT, follow_redirects=True
        ) as client:
            resp = await client.get(_OEMBED_URL, params={"url": url, "format": "json"})
            resp.raise_for_status()
            title = str(resp.json().get("title", "")).strip()
            return title[:256] if title else fallback
    except Exception:  # title is non-essential; fall back silently
        return fallback


def _text_to_pages(text: str) -> list[PageText]:
    """Group transcript words into ~_SECTION_TARGET_CHARS sections."""
    pages: list[PageText] = []
    bucket: list[str] = []
    bucket_len = 0
    for word in text.split():
        bucket.append(word)
        bucket_len += len(word) + 1
        if bucket_len >= _SECTION_TARGET_CHARS:
            pages.append(PageText(page=len(pages) + 1, text=" ".join(bucket)))
            bucket = []
            bucket_len = 0
    if bucket:
        pages.append(PageText(page=len(pages) + 1, text=" ".join(bucket)))
    return pages or [PageText(page=1, text=text)]
