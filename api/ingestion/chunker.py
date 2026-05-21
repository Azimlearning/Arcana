"""Fixed-window chunker with paragraph/sentence-aware boundaries (FR-ING-05).

Joins all pages into one text stream with `\\n\\n` page separators (so the
chunker can find paragraph boundaries naturally), then slides a window of
`target_chars` with `overlap_chars` of carry. Within each window, prefers
to break on a paragraph boundary (`\\n\\n`), else a sentence boundary
(`. `), else a hard character cut.

Each chunk records the page on which it *starts* — citation accuracy is
keyed off that, so chunks spanning page boundaries are correctly attributed
to where their lead sentence lives.
"""

from __future__ import annotations

from bisect import bisect_right

from api.ingestion.types import Chunk, PageText, make_chunk_id

DEFAULT_TARGET_CHARS = 1200
DEFAULT_OVERLAP_CHARS = 200
PAGE_SEPARATOR = "\n\n"
# Within `BOUNDARY_LOOKBACK` chars from the window end, prefer a real
# paragraph or sentence boundary over a hard char cut.
BOUNDARY_LOOKBACK = 200


def chunk(
    pages: list[PageText],
    *,
    doc_id: str,
    target_chars: int = DEFAULT_TARGET_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[Chunk]:
    if target_chars < 1:
        raise ValueError(f"target_chars must be >= 1 (got {target_chars})")
    if overlap_chars < 0 or overlap_chars >= target_chars:
        raise ValueError(
            f"overlap_chars must be in [0, target_chars) "
            f"(got {overlap_chars} with target {target_chars})"
        )
    if not pages:
        return []

    # Build one text stream + a parallel offset index for page attribution.
    full_text, page_breakpoints = _flatten(pages)
    if not full_text.strip():
        return []

    chunks: list[Chunk] = []
    pos = 0
    while pos < len(full_text):
        # Skip leading whitespace so we don't emit pure-whitespace chunks.
        while pos < len(full_text) and full_text[pos].isspace():
            pos += 1
        if pos >= len(full_text):
            break

        end = min(pos + target_chars, len(full_text))

        if end < len(full_text):
            end = _prefer_clean_boundary(full_text, pos, end)

        text = full_text[pos:end].strip()
        if text:
            page = _page_for_offset(pos, page_breakpoints)
            chunks.append(
                Chunk(
                    id=make_chunk_id(doc_id=doc_id, page=page, char_offset=pos, text=text),
                    doc_id=doc_id,
                    text=text,
                    page=page,
                    char_offset=pos,
                )
            )

        if end >= len(full_text):
            break
        # Advance the window by (target - overlap); guard against zero-progress.
        next_pos = end - overlap_chars
        pos = next_pos if next_pos > pos else end

    return chunks


# ── Internals ─────────────────────────────────────────────────────


def _flatten(pages: list[PageText]) -> tuple[str, list[tuple[int, int]]]:
    """Concatenate page texts with `PAGE_SEPARATOR`. Return
    `(full_text, [(start_offset, page_number), ...])`."""
    parts: list[str] = []
    breakpoints: list[tuple[int, int]] = []
    cursor = 0
    for p in pages:
        breakpoints.append((cursor, p.page))
        parts.append(p.text)
        cursor += len(p.text)
        parts.append(PAGE_SEPARATOR)
        cursor += len(PAGE_SEPARATOR)
    # Drop the trailing separator so `len(full_text)` matches the index.
    full = "".join(parts)
    if full.endswith(PAGE_SEPARATOR):
        full = full[: -len(PAGE_SEPARATOR)]
    return full, breakpoints


def _prefer_clean_boundary(text: str, start: int, end: int) -> int:
    """Nudge `end` backward to a paragraph or sentence boundary, but only
    if doing so still produces a chunk at least half the target window —
    a paragraph break at `start + 2` would yield a 2-char chunk and a
    catastrophically large next one. Hard-cut beats a degenerate split."""
    target = end - start
    min_acceptable = start + max(1, target // 2)
    window_lo = max(min_acceptable, end - BOUNDARY_LOOKBACK)
    para = text.rfind("\n\n", window_lo, end)
    if para != -1:
        return para
    sent = text.rfind(". ", window_lo, end)
    if sent != -1:
        return sent + 2  # include the period; cut after the space
    return end  # no clean boundary available — hard cut


def _page_for_offset(offset: int, breakpoints: list[tuple[int, int]]) -> int:
    """Binary-search the page number whose text starts at or before `offset`."""
    starts = [bp[0] for bp in breakpoints]
    idx = bisect_right(starts, offset) - 1
    if idx < 0:
        idx = 0
    return breakpoints[idx][1]
