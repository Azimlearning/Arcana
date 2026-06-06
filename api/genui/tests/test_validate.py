"""validate_block - happy path, schema drift, fail-closed semantics."""

from __future__ import annotations

import pytest

from api.core.errors import ValidationFailed
from api.genui._generated import (
    BlockMeta,
    CitedSummary,
    CitedSummaryData,
    SummarySegment,
)
from api.genui.validate import validate_block


def _ok_payload() -> dict:
    return {
        "type": "CitedSummary",
        "id": "block_001",
        "meta": {"panel": "chat", "order": 0, "status": "ready"},
        "data": {
            "summary": "answer with [c1]",
            "segments": [{"text": "answer with", "citationIds": ["c1"]}],
            "citations": [
                {
                    "id": "c1",
                    "docId": "doc_a",
                    "docTitle": "Doc A",
                    "page": 4,
                    "quote": "supporting quote",
                }
            ],
        },
    }


def _source() -> dict:
    return {"id": "c1", "docId": "d1", "docTitle": "T", "page": 1, "quote": "q"}


def test_valid_dict_passes_through():
    out = validate_block(_ok_payload())
    assert isinstance(out, CitedSummary)
    assert out.id == "block_001"
    assert out.data.summary == "answer with [c1]"


def test_valid_pydantic_instance_revalidated():
    block = CitedSummary(
        type="CitedSummary",
        id="block_002",
        meta=BlockMeta(panel="chat", order=0, status="ready"),
        data=CitedSummaryData(
            summary="hi",
            segments=[SummarySegment(text="hi", citationIds=[])],
            citations=[],
        ),
    )
    out = validate_block(block)
    assert out.id == "block_002"


def test_missing_required_field_raises_validation_failed():
    bad = _ok_payload()
    del bad["meta"]
    with pytest.raises(ValidationFailed) as exc:
        validate_block(bad)
    assert exc.value.code == "validation_failed"
    assert "meta" in str(exc.value.details["errors"])


def test_wrong_discriminator_raises():
    bad = _ok_payload()
    bad["type"] = "UnknownBlock"   # not in the current union
    with pytest.raises(ValidationFailed):
        validate_block(bad)


def test_invalid_panel_value_raises():
    bad = _ok_payload()
    bad["meta"]["panel"] = "studio_left"   # not a valid Panel literal
    with pytest.raises(ValidationFailed):
        validate_block(bad)


def test_nested_citation_type_mismatch_raises():
    bad = _ok_payload()
    bad["data"]["citations"][0]["page"] = "four"   # str where int expected
    with pytest.raises(ValidationFailed):
        validate_block(bad)


def test_error_envelope_lists_field_paths():
    bad = _ok_payload()
    del bad["meta"]
    del bad["data"]["citations"]
    with pytest.raises(ValidationFailed) as exc:
        validate_block(bad)
    locs = {tuple(e["loc"]) for e in exc.value.details["errors"]}
    # Each missing field should appear in `loc`.
    assert any("meta" in loc for loc in locs)
    assert any("citations" in loc for loc in locs)


# ── New block variants (Slice 2) ──────────────────────────────────────────

def test_literature_matrix_validates():
    payload = {
        "type": "LiteratureMatrix",
        "id": "block_lm",
        "meta": {"panel": "studio", "order": 1, "status": "ready"},
        "data": {
            "query": "compare methods",
            "dimensions": ["Methodology", "Sample size"],
            "rows": [
                {
                    "docId": "doc_a",
                    "docTitle": "Paper A",
                    "cells": [
                        {"text": "RCT", "citationId": "c1"},
                        {"text": "200", "citationId": None},
                    ],
                }
            ],
            "citations": [
                {
                    "id": "c1",
                    "docId": "doc_a",
                    "docTitle": "Paper A",
                    "page": 3,
                    "quote": "a randomised controlled trial",
                }
            ],
        },
    }
    from api.genui._generated import LiteratureMatrix
    out = validate_block(payload)
    assert isinstance(out, LiteratureMatrix)
    assert out.data.query == "compare methods"
    assert out.data.rows[0].cells[0].text == "RCT"
    assert out.data.rows[0].cells[1].citationId is None


def test_contradiction_alert_validates():
    payload = {
        "type": "ContradictionAlert",
        "id": "block_ca",
        "meta": {"panel": "chat", "order": 2, "status": "ready"},
        "data": {
            "concept": "dark matter",
            "summary": "Papers disagree on detection method.",
            "claims": [
                {
                    "docId": "doc_a",
                    "docTitle": "Paper A",
                    "stance": "direct detection is viable",
                    "quote": "direct detection experiments show promise",
                },
                {
                    "docId": "doc_b",
                    "docTitle": "Paper B",
                    "stance": "indirect detection is more reliable",
                    "quote": "indirect signals are more consistent",
                },
            ],
        },
    }
    from api.genui._generated import ContradictionAlert
    out = validate_block(payload)
    assert isinstance(out, ContradictionAlert)
    assert out.data.concept == "dark matter"
    assert len(out.data.claims) == 2


def test_gap_analysis_validates():
    payload = {
        "type": "GapAnalysis",
        "id": "block_ga",
        "meta": {"panel": "studio", "order": 3, "status": "ready"},
        "data": {
            "summary": "The corpus lacks coverage of practical applications.",
            "gaps": [
                {
                    "label": "Clinical trials",
                    "description": "No papers discuss Phase III trials.",
                    "severity": "high",
                }
            ],
            "coveredTopics": ["basic science", "theory"],
        },
    }
    from api.genui._generated import GapAnalysis
    out = validate_block(payload)
    assert isinstance(out, GapAnalysis)
    assert out.data.gaps[0].severity == "high"


def test_insight_card_validates():
    payload = {
        "type": "InsightCard",
        "id": "block_ic",
        "meta": {"panel": "chat", "order": 4, "status": "ready"},
        "data": {
            "insight": "Both papers use the same dataset.",
            "connection": "Shared experimental corpus",
            "docAId": "doc_a",
            "docATitle": "Paper A",
            "docBId": "doc_b",
            "docBTitle": "Paper B",
            "citations": [],
        },
    }
    from api.genui._generated import InsightCard
    out = validate_block(payload)
    assert isinstance(out, InsightCard)
    assert out.data.docATitle == "Paper A"


def test_knowledge_graph_view_validates():
    payload = {
        "type": "KnowledgeGraphView",
        "id": "block_kg",
        "meta": {"panel": "studio", "order": 5, "status": "ready"},
        "data": {
            "nodes": [
                {"id": "n1", "label": "BERT", "nodeType": "concept"},
                {"id": "n2", "label": "Transformers", "nodeType": "concept"},
            ],
            "edges": [
                {"source": "n1", "target": "n2", "relation": "based_on"}
            ],
        },
    }
    from api.genui._generated import KnowledgeGraphView
    out = validate_block(payload)
    assert isinstance(out, KnowledgeGraphView)
    assert out.data.focusNodeId is None
    assert len(out.data.nodes) == 2


def test_knowledge_graph_view_with_focus_node():
    payload = {
        "type": "KnowledgeGraphView",
        "id": "block_kg2",
        "meta": {"panel": "studio", "order": 6, "status": "ready"},
        "data": {
            "nodes": [{"id": "n1", "label": "BERT", "nodeType": "concept"}],
            "edges": [],
            "focusNodeId": "n1",
        },
    }
    from api.genui._generated import KnowledgeGraphView
    out = validate_block(payload)
    assert isinstance(out, KnowledgeGraphView)
    assert out.data.focusNodeId == "n1"


def test_gap_severity_invalid_raises():
    payload = {
        "type": "GapAnalysis",
        "id": "block_bad",
        "meta": {"panel": "studio", "order": 0, "status": "ready"},
        "data": {
            "summary": "x",
            "gaps": [{"label": "x", "description": "y", "severity": "critical"}],
            "coveredTopics": [],
        },
    }
    with pytest.raises(ValidationFailed):
        validate_block(payload)


# ── New block variants (Slice 3) ──────────────────────────────────────────

def test_flashcard_deck_validates():
    payload = {
        "type": "FlashcardDeck",
        "id": "block_fd",
        "meta": {"panel": "chat", "order": 7, "status": "ready"},
        "data": {
            "topic": "Neural Networks",
            "cards": [
                {
                    "front": "What is backpropagation?",
                    "back": "Gradient computation via chain rule.",
                    "source": _source(),
                    "schedule": None,
                }
            ],
            "totalCards": 1,
            "dueCount": 0,
        },
    }
    from api.genui._generated import FlashcardDeck
    out = validate_block(payload)
    assert isinstance(out, FlashcardDeck)
    assert out.data.topic == "Neural Networks"
    assert len(out.data.cards) == 1
    assert out.data.cards[0].schedule is None


def test_quiz_card_validates():
    payload = {
        "type": "QuizCard",
        "id": "block_qc",
        "meta": {"panel": "chat", "order": 8, "status": "ready"},
        "data": {
            "question": "What does ReLU stand for?",
            "questionType": "mcq",
            "options": [
                {"index": 0, "text": "Rectified Linear Unit"},
                {"index": 1, "text": "Random Layer Unit"},
                {"index": 2, "text": "Relative Learning Unit"},
                {"index": 3, "text": "None"},
            ],
            "correctIndex": 0,
            "explanation": "ReLU = Rectified Linear Unit.",
            "difficulty": "recall",
            "source": _source(),
        },
    }
    from api.genui._generated import QuizCard
    out = validate_block(payload)
    assert isinstance(out, QuizCard)
    assert out.data.question.startswith("What does")
    assert out.data.correctIndex == 0
    assert len(out.data.options) == 4


def test_socratic_dialog_validates():
    payload = {
        "type": "SocraticDialog",
        "id": "block_sd",
        "meta": {"panel": "chat", "order": 9, "status": "ready"},
        "data": {
            "concept": "backpropagation",
            "turns": [
                {"role": "tutor", "text": "What do you think a forward pass does?"},
                {"role": "learner", "text": "It calculates the output?"},
            ],
            "nextQuestion": "And what happens to the error after the output is computed?",
            "bloomLevel": "comprehension",
        },
    }
    from api.genui._generated import SocraticDialog
    out = validate_block(payload)
    assert isinstance(out, SocraticDialog)
    assert out.data.concept == "backpropagation"
    assert len(out.data.turns) == 2
    assert out.data.nextQuestion.endswith("?")
    assert out.data.bloomLevel == "comprehension"


def test_feynman_explainer_validates():
    payload = {
        "type": "FeynmanExplainer",
        "id": "block_fe",
        "meta": {"panel": "chat", "order": 10, "status": "ready"},
        "data": {
            "concept": "attention mechanism",
            "explanation": "Imagine each word voting on which other words matter most.",
            "gaps": ["Does not explain multi-head attention.", "Omits positional encoding."],
            "source": _source(),
        },
    }
    from api.genui._generated import FeynmanExplainer
    out = validate_block(payload)
    assert isinstance(out, FeynmanExplainer)
    assert out.data.concept == "attention mechanism"
    assert len(out.data.gaps) == 2


def test_quiz_card_short_answer_validates():
    """QuizCard with short_answer type: options empty, correctIndex None."""
    payload = {
        "type": "QuizCard",
        "id": "block_sa",
        "meta": {"panel": "chat", "order": 11, "status": "ready"},
        "data": {
            "question": "Define gradient descent in one sentence.",
            "questionType": "short_answer",
            "options": [],
            "correctIndex": None,
            "explanation": "An iterative optimisation algorithm.",
            "difficulty": "comprehension",
            "source": _source(),
        },
    }
    from api.genui._generated import QuizCard
    out = validate_block(payload)
    assert isinstance(out, QuizCard)
    assert out.data.correctIndex is None
    assert out.data.questionType == "short_answer"


# ── New block variants (Slice 4) ──────────────────────────────────────────

def test_draft_editor_validates():
    payload = {
        "type": "DraftEditor",
        "id": "block_de",
        "meta": {"panel": "chat", "order": 12, "status": "ready"},
        "data": {
            "title": "Attention Mechanisms in NLP",
            "sections": [
                {"heading": "Introduction", "body": "Transformers rely on self-attention [c1].", "citationIds": ["c1"]},
                {"heading": "Key Mechanism", "body": "Queries and keys are projected linearly [c1].", "citationIds": ["c1"]},
            ],
            "citations": [_source()],
            "wordCount": 14,
        },
    }
    from api.genui._generated import DraftEditor
    out = validate_block(payload)
    assert isinstance(out, DraftEditor)
    assert out.data.title == "Attention Mechanisms in NLP"
    assert len(out.data.sections) == 2
    assert out.data.wordCount == 14


def test_draft_editor_empty_sections_validates():
    payload = {
        "type": "DraftEditor",
        "id": "block_de2",
        "meta": {"panel": "chat", "order": 13, "status": "error"},
        "data": {"title": "Draft failed", "sections": [], "citations": [], "wordCount": 0},
    }
    from api.genui._generated import DraftEditor
    out = validate_block(payload)
    assert isinstance(out, DraftEditor)
    assert out.data.wordCount == 0
