"""Entity extractor — JSON parsing robustness, slug canonicalisation,
relationship validation, edge cases."""

from __future__ import annotations

import pytest

from api.core.errors import IngestFailed
from api.ingestion.extractor import (
    ExtractionResult,
    _build_result,
    _parse_json,
    _slug,
    extract_entities,
)
from api.llm.types import Completion, Usage

# ── Slug + dedupe ─────────────────────────────────────────────────


@pytest.mark.parametrize("label,expected", [
    ("graph rag", "graph_rag"),
    ("GraphRAG", "graph_rag"),       # CamelCase split + lowercase = same slug
    ("Graph RAG", "graph_rag"),
    ("graph_rag", "graph_rag"),
    ("vector retrieval", "vector_retrieval"),
    ("XMLParser", "xml_parser"),     # Acronym-then-Word boundary
    ("  cohort  ", "cohort"),
    ("punc!tu@tion", "punc_tu_tion"),
    ("", "unknown"),
    ("___", "unknown"),
    # FR-ING-09 plural folding: variants collapse to one node id.
    ("knowledge graphs", "knowledge_graph"),
    ("knowledge graph", "knowledge_graph"),
    ("neural networks", "neural_network"),
    ("transformers", "transformer"),
    ("ontologies", "ontology"),
    ("classes", "class"),
    # guarded non-plurals must be left intact
    ("bias", "bias"),
    ("analysis", "analysis"),
    ("corpus", "corpus"),
    ("process", "process"),
])
def test_slug_canonicalises_consistently(label, expected):
    assert _slug(label) == expected


def test_slug_collapses_singular_and_plural_to_one_id():
    """Same concept written singular vs plural -> identical node id (FR-ING-09)."""
    assert _slug("Knowledge Graphs") == _slug("knowledge graph")
    assert _slug("Vector Databases") == _slug("vector database")


# ── JSON parser ──────────────────────────────────────────────────


def test_parse_json_plain_object():
    out = _parse_json('{"entities": [], "relationships": []}')
    assert out == {"entities": [], "relationships": []}


def test_parse_json_strips_markdown_fences():
    raw = '```json\n{"entities": [{"label": "x", "type": "Concept"}]}\n```'
    out = _parse_json(raw)
    assert len(out["entities"]) == 1


def test_parse_json_strips_leading_prose():
    raw = 'Here is the JSON you asked for:\n{"entities": []}'
    out = _parse_json(raw)
    assert out == {"entities": []}


def test_parse_json_raises_on_garbage():
    with pytest.raises(IngestFailed):
        _parse_json("definitely not json")


def test_parse_json_raises_on_array_at_top_level():
    with pytest.raises(IngestFailed):
        _parse_json("[1, 2, 3]")


# ── Result builder ────────────────────────────────────────────────


def test_build_result_dedupes_by_slug():
    """`graph rag` and `GraphRAG` collapse to one node by slug."""
    parsed = {
        "entities": [
            {"label": "graph rag", "type": "Concept"},
            {"label": "GraphRAG", "type": "Concept"},
        ],
        "relationships": [],
    }
    result = _build_result(parsed, chunk_id="c1", doc_id="d1")
    assert len(result.nodes) == 1
    assert result.nodes[0].id == "graph_rag"


def test_build_result_rejects_invalid_entity_types():
    parsed = {
        "entities": [
            {"label": "valid", "type": "Concept"},
            {"label": "bogus", "type": "RandomType"},
        ],
        "relationships": [],
    }
    result = _build_result(parsed, chunk_id="c1", doc_id="d1")
    assert len(result.nodes) == 1
    assert result.nodes[0].label == "valid"


def test_build_result_rejects_self_loops():
    parsed = {
        "entities": [{"label": "x", "type": "Concept"}],
        "relationships": [{"src": "x", "dst": "x", "type": "AGREES_WITH"}],
    }
    result = _build_result(parsed, chunk_id="c1", doc_id="d1")
    assert result.edges == []


def test_build_result_rejects_unreferenced_relationship_endpoints():
    """Relationship referencing an entity that's not in the entities list
    is dropped (LLM forgot to declare it)."""
    parsed = {
        "entities": [{"label": "x", "type": "Concept"}],
        "relationships": [{"src": "x", "dst": "y_not_listed", "type": "EXTENDS"}],
    }
    result = _build_result(parsed, chunk_id="c1", doc_id="d1")
    assert result.edges == []


def test_build_result_rejects_lowercase_relation_type():
    parsed = {
        "entities": [
            {"label": "a", "type": "Concept"},
            {"label": "b", "type": "Concept"},
        ],
        "relationships": [{"src": "a", "dst": "b", "type": "extends"}],
    }
    result = _build_result(parsed, chunk_id="c1", doc_id="d1")
    assert result.edges == []


def test_build_result_dedupes_edges():
    parsed = {
        "entities": [
            {"label": "a", "type": "Concept"},
            {"label": "b", "type": "Concept"},
        ],
        "relationships": [
            {"src": "a", "dst": "b", "type": "EXTENDS"},
            {"src": "a", "dst": "b", "type": "EXTENDS"},
        ],
    }
    result = _build_result(parsed, chunk_id="c1", doc_id="d1")
    assert len(result.edges) == 1


def test_build_result_stamps_provenance_on_nodes():
    parsed = {"entities": [{"label": "x", "type": "Concept"}], "relationships": []}
    result = _build_result(parsed, chunk_id="ch1", doc_id="doc_alpha")
    node = result.nodes[0]
    assert node.properties["mentioned_in_chunks"] == ["ch1"]
    assert node.properties["doc_ids"] == ["doc_alpha"]


# ── Full extract_entities (LLM-driven) ──────────────────────────


class _StubLLM:
    """Returns a configurable canned JSON response."""

    def __init__(self, *, text: str, raise_exc: Exception | None = None) -> None:
        self._text = text
        self._raise = raise_exc

    async def complete(self, messages, *, system=None, tools=None, max_tokens=None, budget=None):
        if self._raise:
            raise self._raise
        return Completion(
            text=self._text,
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=20),
            model="stub", provider="stub",
        )


async def test_extract_returns_empty_for_blank_text():
    result = await extract_entities(
        text="   \n  ", chunk_id="c1", doc_id="d1",
        llm=_StubLLM(text='{"entities": [], "relationships": []}'),  # type: ignore[arg-type]
    )
    assert result == ExtractionResult(nodes=[], edges=[])


async def test_extract_happy_path():
    response = """{
      "entities": [
        {"label": "graph rag", "type": "Concept"},
        {"label": "vector retrieval", "type": "Concept"}
      ],
      "relationships": [
        {"src": "graph rag", "dst": "vector retrieval", "type": "CONTRASTS_WITH"}
      ]
    }"""
    result = await extract_entities(
        text="Some passage about GraphRAG vs vector retrieval.",
        chunk_id="c1", doc_id="d1",
        llm=_StubLLM(text=response),  # type: ignore[arg-type]
    )
    assert {n.id for n in result.nodes} == {"graph_rag", "vector_retrieval"}
    assert len(result.edges) == 1
    edge = result.edges[0]
    assert edge.src == "graph_rag"
    assert edge.dst == "vector_retrieval"
    assert edge.type == "CONTRASTS_WITH"


async def test_extract_raises_ingestfailed_on_llm_outage():
    with pytest.raises(IngestFailed) as exc:
        await extract_entities(
            text="x", chunk_id="c1", doc_id="d1",
            llm=_StubLLM(text="(unused)", raise_exc=RuntimeError("api down")),  # type: ignore[arg-type]
        )
    assert "LLM call failed" in str(exc.value)


async def test_extract_raises_ingestfailed_on_bad_json():
    with pytest.raises(IngestFailed):
        await extract_entities(
            text="x", chunk_id="c1", doc_id="d1",
            llm=_StubLLM(text="not json at all"),  # type: ignore[arg-type]
        )
