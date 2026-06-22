"""Tests for the YouTube transcript parser (FR-ING-03).

Patches the transcript fetch + oEmbed title seams so no real network
calls are made. Mirrors the web-parser test style.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from api.core.errors import IngestFailed
from api.ingestion.parsers import youtube
from api.ingestion.parsers.youtube import doc_id_for_url, extract_video_id, fetch_and_parse


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=abc123XYZ_-&t=42s", "abc123XYZ_-"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_extract_video_id_forms(url: str, expected: str) -> None:
    assert extract_video_id(url) == expected


def test_extract_video_id_rejects_non_youtube() -> None:
    with pytest.raises(IngestFailed):
        extract_video_id("https://example.com/watch?v=nope")


def test_doc_id_is_stable_and_prefixed() -> None:
    did = doc_id_for_url("https://youtu.be/dQw4w9WgXcQ")
    assert did == "yt_dQw4w9WgXcQ"
    assert did == doc_id_for_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


@pytest.mark.asyncio
async def test_fetch_and_parse_returns_title_and_pages() -> None:
    segments = [{"text": f"word{i}"} for i in range(800)]
    with (
        patch.object(youtube, "_fetch_transcript", return_value=segments),
        patch.object(youtube, "_fetch_title", new=AsyncMock(return_value="A Lecture")),
    ):
        title, pages = await fetch_and_parse("https://youtu.be/dQw4w9WgXcQ")

    assert title == "A Lecture"
    assert len(pages) >= 1
    assert pages[0].page == 1
    assert "word0" in pages[0].text
    # transcript joined into one body, re-sectioned into ~1500-char pages
    assert all(p.text.strip() for p in pages)


@pytest.mark.asyncio
async def test_fetch_and_parse_raises_on_empty_transcript() -> None:
    with patch.object(youtube, "_fetch_transcript", return_value=[]):
        with pytest.raises(IngestFailed):
            await fetch_and_parse("https://youtu.be/dQw4w9WgXcQ")


@pytest.mark.asyncio
async def test_fetch_and_parse_raises_on_whitespace_only_transcript() -> None:
    with patch.object(youtube, "_fetch_transcript", return_value=[{"text": "   "}]):
        with pytest.raises(IngestFailed):
            await fetch_and_parse("https://youtu.be/dQw4w9WgXcQ")
