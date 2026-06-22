"""Entity + relationship extraction — FR-ING-06, FR-ING-09.

Calls the LLM with a JSON-only extraction prompt, parses the response,
and returns typed `GraphNode` + `GraphEdge` instances ready for the
GraphStore. Canonicalisation is slug-based (label → lowercase → snake_case
slug) so multiple chunks mentioning the same concept collapse to one
node id. Embedding-similarity canonicalisation arrives in P1 §1.2.

Defensive parsing tolerates common LLM JSON-formatting glitches:
markdown fences, leading prose, trailing prose - the parser walks the
text and extracts the first balanced `{...}` block.

Per-chunk extraction is isolated: a malformed LLM response on one chunk
raises `IngestFailed`, but the ingestion pipeline catches it so the rest
of the document still ingests (vector + chunk store remain populated).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from api.core.errors import IngestFailed
from api.core.logging import get_logger
from api.llm.prompts.extraction import EXTRACTION_SYSTEM, build_user_prompt
from api.llm.service import LLMService
from api.llm.types import Message
from api.stores.graph_store import GraphEdge, GraphNode

logger = get_logger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")
# CamelCase / PascalCase splitter — applied BEFORE lowercasing so e.g.
# "GraphRAG" and "graph rag" both collapse to the same `graph_rag` slug.
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_ACRONYM_BOUNDARY_RE = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")
_VALID_TYPES = {"Concept", "Person", "Document", "Topic"}
_VALID_RELATION_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Common non-plural or irregular "-s" words that must NOT be singularised
# (FR-ING-09 plural folding is heuristic; these are the frequent traps).
_PLURAL_EXCEPTIONS = frozenset({
    "bias", "lens", "series", "species", "news",
    "physics", "mathematics", "statistics", "kudos", "data",
})


@dataclass(frozen=True)
class ExtractionResult:
    """Output of one chunk's extraction pass. Nodes carry first-mention
    chunk + doc ids in their properties; the pipeline merges across
    chunks via `GraphStore.get_node`."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


def _slug(label: str) -> str:
    """Canonicalise a label to a stable node-id slug.

    Pipeline:
      1. Strip surrounding whitespace.
      2. Split CamelCase / PascalCase boundaries with `_` (so "GraphRAG"
         and "graph rag" both collapse to `graph_rag`).
      3. Lowercase + replace runs of non-alphanum with `_`.
      4. Strip leading/trailing underscores.

    Returns `"unknown"` for all-non-alphanum input — empty would fail
    GraphStore validation downstream.
    """
    s = label.strip()
    s = _CAMEL_BOUNDARY_RE.sub("_", s)
    s = _ACRONYM_BOUNDARY_RE.sub("_", s)
    s = _SLUG_RE.sub("_", s.lower()).strip("_")
    if not s:
        return "unknown"
    # FR-ING-09: fold the head (final) token to singular so "knowledge
    # graphs" and "knowledge graph" collapse to one node id.
    parts = s.split("_")
    parts[-1] = _singularise(parts[-1])
    return "_".join(parts) or "unknown"


def _singularise(token: str) -> str:
    """Best-effort singular of a head token (FR-ING-09).

    Deliberately conservative: guarded against common non-plural "-s"
    words (process, corpus, analysis, bias, ...) and irregulars. Handles
    the frequent academic cases — "graphs"->"graph", "ontologies"->
    "ontology", "classes"->"class". Embedding-similarity merging of true
    synonyms remains future work (§1.2)."""
    t = token
    if len(t) < 4 or t in _PLURAL_EXCEPTIONS:
        return t
    if t.endswith(("ss", "us", "is", "os")):        # process, corpus, analysis, chaos
        return t
    if t.endswith("ies") and len(t) > 4:            # ontologies -> ontology
        return t[:-3] + "y"
    if t.endswith(("sses", "shes", "ches", "xes", "zzes")):  # classes->class, boxes->box
        return t[:-2]
    if t.endswith("s"):                             # graphs->graph, databases->database
        return t[:-1]
    return t


async def extract_entities(
    *,
    text: str,
    chunk_id: str,
    doc_id: str,
    llm: LLMService,
) -> ExtractionResult:
    """Run one extraction pass against `text`. Returns nodes + edges with
    chunk+doc provenance attached. Empty input returns empty result."""
    if not text or not text.strip():
        return ExtractionResult(nodes=[], edges=[])

    try:
        completion = await llm.complete(
            messages=[Message(role="user", content=build_user_prompt(text))],
            system=EXTRACTION_SYSTEM,
            max_tokens=1024,
        )
    except Exception as e:
        raise IngestFailed(f"extraction LLM call failed: {e}") from e

    parsed = _parse_json(completion.text)
    return _build_result(parsed, chunk_id=chunk_id, doc_id=doc_id)


def _parse_json(raw: str) -> dict:
    """Defensive JSON parse. Strips ```json fences, finds the first
    balanced `{...}` block, and raises `IngestFailed` on anything else."""
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)

    first = s.find("{")
    last = s.rfind("}")
    if first == -1 or last == -1 or last <= first:
        raise IngestFailed(f"extraction returned no JSON object: {raw[:200]!r}")
    fragment = s[first : last + 1]
    try:
        parsed = json.loads(fragment)
    except json.JSONDecodeError as e:
        raise IngestFailed(
            f"extraction JSON parse failed: {e}; raw={raw[:200]!r}"
        ) from e
    if not isinstance(parsed, dict):
        raise IngestFailed(f"extraction returned non-object: {raw[:200]!r}")
    return parsed


def _build_result(
    parsed: dict,
    *,
    chunk_id: str,
    doc_id: str,
) -> ExtractionResult:
    entities_raw = parsed.get("entities", [])
    relationships_raw = parsed.get("relationships", [])

    # First pass: collect valid entities and their slug map. Dedupe by
    # slug so two near-duplicate labels ("graph rag", "graphrag") collapse.
    label_to_slug: dict[str, str] = {}
    nodes_by_slug: dict[str, GraphNode] = {}

    for entity in entities_raw:
        if not isinstance(entity, dict):
            continue
        raw_label = str(entity.get("label", "")).strip()
        etype = str(entity.get("type", "Concept"))
        if not raw_label or etype not in _VALID_TYPES:
            continue
        # `_slug` needs the original case so the CamelCase splitter can
        # work (e.g. "GraphRAG" -> "graph_rag"). Lowercase the lookup key
        # so relationships referencing the entity match regardless of case.
        slug = _slug(raw_label)
        label_lc = raw_label.lower()
        if slug in nodes_by_slug:
            # Keep the first label seen; map the duplicate label to the
            # same slug so relationships referencing it still resolve.
            label_to_slug[label_lc] = slug
            continue
        label_to_slug[label_lc] = slug
        nodes_by_slug[slug] = GraphNode(
            id=slug,
            type=etype,
            label=label_lc,
            properties={
                "mentioned_in_chunks": [chunk_id],
                "doc_ids": [doc_id],
            },
        )

    # Second pass: validate relationships against the kept entity set.
    edges: list[GraphEdge] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for rel in relationships_raw:
        if not isinstance(rel, dict):
            continue
        src_label = str(rel.get("src", "")).strip().lower()
        dst_label = str(rel.get("dst", "")).strip().lower()
        rtype = str(rel.get("type", "")).strip()
        if not src_label or not dst_label or not _VALID_RELATION_RE.match(rtype):
            continue
        src_slug = label_to_slug.get(src_label)
        dst_slug = label_to_slug.get(dst_label)
        if not src_slug or not dst_slug or src_slug == dst_slug:
            # Skip relationships referencing entities the LLM forgot to
            # list in `entities`, or self-loops.
            continue
        edge_key = (src_slug, dst_slug, rtype)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        edges.append(GraphEdge(src=src_slug, dst=dst_slug, type=rtype))

    return ExtractionResult(nodes=list(nodes_by_slug.values()), edges=edges)
