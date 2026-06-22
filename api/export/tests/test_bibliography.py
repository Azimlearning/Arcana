"""Bibliography export — BibTeX + RIS formatting (FR-EXP-08)."""

from __future__ import annotations

from api.export.bibliography import CitationEntry, make_key, to_bibtex, to_ris

_BS = chr(92)  # backslash, kept out of literals to avoid escaping noise
_E = CitationEntry(key="GraphRag2024", title="GraphRAG & Retrieval", url="https://x.org/a", accessed="2026-06-22")


def test_make_key_is_alphanumeric_and_stable():
    k = make_key("doc_alpha-1", "Some Title")
    assert k.isalnum()
    assert make_key("doc_alpha-1", "Some Title") == k


def test_bibtex_entry_shape_and_escaping():
    out = to_bibtex([_E])
    assert out.startswith("@misc{GraphRag2024,")
    assert ("title = {GraphRAG " + _BS + "& Retrieval}") in out          # & escaped
    assert ("howpublished = {" + _BS + "url{https://x.org/a}}") in out
    assert "urldate = {2026-06-22}" in out
    assert out.rstrip().endswith("}")


def test_ris_entry_shape():
    out = to_ris([_E])
    assert "TY  - GEN" in out
    assert "TI  - GraphRAG & Retrieval" in out
    assert "UR  - https://x.org/a" in out
    assert out.rstrip().endswith("ER  -")


def test_empty_input_is_empty_string():
    assert to_bibtex([]) == ""
    assert to_ris([]) == ""
