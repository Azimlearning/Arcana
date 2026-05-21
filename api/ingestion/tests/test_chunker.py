"""Chunker — window math, boundary preference, edge cases, id determinism."""

from __future__ import annotations

import pytest

from api.ingestion.chunker import chunk
from api.ingestion.types import PageText, make_chunk_id


def _page(num: int, text: str) -> PageText:
    return PageText(page=num, text=text)


def test_empty_input_returns_empty():
    assert chunk([], doc_id="d1") == []


def test_whitespace_only_input_returns_empty():
    assert chunk([_page(1, "   \n\n  ")], doc_id="d1") == []


def test_short_text_produces_single_chunk():
    pages = [_page(1, "Hello world. Just a short body.")]
    chunks = chunk(pages, doc_id="d1", target_chars=1200)
    assert len(chunks) == 1
    assert chunks[0].text == "Hello world. Just a short body."
    assert chunks[0].page == 1
    assert chunks[0].char_offset == 0
    assert chunks[0].doc_id == "d1"


def test_long_text_splits_with_overlap():
    body = ("Word " * 600).strip()   # ~3000 chars
    chunks = chunk([_page(1, body)], doc_id="d1", target_chars=1200, overlap_chars=200)
    assert len(chunks) >= 2
    # Each chunk should be at most target_chars long-ish (boundary nudges allowed).
    for c in chunks:
        assert len(c.text) <= 1300  # target + small slack from boundary preference


def test_prefers_paragraph_boundary():
    para_a = "Alpha. " * 100  # ~700 chars
    para_b = "Beta. " * 100   # ~600 chars
    body = para_a + "\n\n" + para_b
    chunks = chunk([_page(1, body)], doc_id="d1", target_chars=750, overlap_chars=50)
    # First chunk should end at or before the paragraph break — i.e. not split
    # a sentence across the break.
    assert chunks[0].text.endswith("Alpha.") or chunks[0].text.endswith("Alpha. ")


def test_prefers_sentence_boundary_when_no_paragraph():
    body = ("Sentence one. " * 100).strip()
    chunks = chunk([_page(1, body)], doc_id="d1", target_chars=500, overlap_chars=50)
    # All chunks should end at a sentence terminator (modulo the last one).
    for c in chunks[:-1]:
        assert c.text.rstrip().endswith(".")


def test_page_attribution_across_pages():
    """A chunk that starts on page 2 carries `page=2` even if pages 1+2 flow together."""
    p1 = _page(1, "Page one body. " * 50)   # ~750 chars
    p2 = _page(2, "Page two body. " * 50)   # ~750 chars
    chunks = chunk([p1, p2], doc_id="d1", target_chars=400, overlap_chars=50)
    pages_used = {c.page for c in chunks}
    assert pages_used == {1, 2}
    assert chunks[0].page == 1
    assert chunks[-1].page == 2


def test_invalid_target_chars_rejected():
    with pytest.raises(ValueError):
        chunk([_page(1, "x")], doc_id="d1", target_chars=0)


@pytest.mark.parametrize("overlap", [-1, 1200, 5000])
def test_invalid_overlap_chars_rejected(overlap):
    with pytest.raises(ValueError):
        chunk([_page(1, "x")], doc_id="d1", target_chars=1200, overlap_chars=overlap)


def test_chunk_ids_deterministic_across_runs():
    pages = [_page(1, "Stable body for hash determinism test." * 10)]
    a = chunk(pages, doc_id="d1", target_chars=200, overlap_chars=20)
    b = chunk(pages, doc_id="d1", target_chars=200, overlap_chars=20)
    assert [c.id for c in a] == [c.id for c in b]


def test_chunk_ids_differ_across_documents():
    pages = [_page(1, "Identical body identical body identical body identical body.")]
    a = chunk(pages, doc_id="d1")
    b = chunk(pages, doc_id="d2")
    assert a[0].text == b[0].text
    assert a[0].id != b[0].id  # doc_id-scoped


def test_chunk_id_changes_when_text_changes():
    a = chunk([_page(1, "Alpha body of text.")], doc_id="d1")
    b = chunk([_page(1, "Alpha body of TEXT.")], doc_id="d1")
    assert a[0].id != b[0].id


def test_chunk_id_helper_format():
    cid = make_chunk_id(doc_id="d1", page=2, char_offset=100, text="hello")
    assert cid.startswith("d1_c_")
    assert len(cid) == len("d1_c_") + 16  # 16 hex chars after the prefix


def test_degenerate_boundary_falls_back_to_hard_cut():
    """A single `. ` at the very start of the lookback window must NOT
    produce a 3-char chunk. The chunker should hard-cut at target instead."""
    # Sentence terminator at offset 1 followed by long filler — without
    # the min-chunk-size floor this would emit "A. " as a 3-char chunk.
    body = "A. " + ("x" * 1200) + " end."
    chunks = chunk([_page(1, body)], doc_id="d1", target_chars=600, overlap_chars=50)
    # No chunk shorter than roughly half the target.
    for c in chunks[:-1]:
        assert len(c.text) >= 200, f"got pathological short chunk: {c.text!r}"
