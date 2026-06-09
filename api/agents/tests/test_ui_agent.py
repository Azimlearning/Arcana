"""UI Agent — block construction, validation, routing, error paths."""

from __future__ import annotations

from api.agents.base import AgentResult, AgentState
from api.agents.tier3.ui_agent import UIAgent
from api.genui._generated import (
    CitedSummary,
    DraftEditor,
    FeynmanExplainer,
    FlashcardDeck,
    QuizCard,
    SocraticDialog,
)


def _research_payload(*, summary: str = "Answer [c1].") -> dict:
    return {
        "summary": summary,
        "segments": [{"text": "Answer", "citationIds": ["c1"]}],
        "citations": [
            {
                "id": "c1",
                "docId": "doc_alpha",
                "docTitle": "Alpha.pdf",
                "page": 4,
                "quote": "supporting quote",
            }
        ],
    }


def _source() -> dict:
    return {"id": "c1", "docId": "d1", "docTitle": "T", "page": 1, "quote": "q"}


async def test_emits_ready_block_for_successful_research():
    state = AgentState(query="x")
    state.agent_results["research"] = AgentResult(
        agent_name="research",
        payload=_research_payload(),
        status="ok",
    )

    agent = UIAgent()
    result = await agent.run("x", state=state)

    assert result.status == "ok"
    assert len(state.ui_blocks) == 1
    block = state.ui_blocks[0]
    assert isinstance(block, CitedSummary)
    assert block.type == "CitedSummary"
    assert block.meta.status == "ready"
    assert block.meta.panel == "chat"
    assert block.id.startswith("block_")
    assert block.data.summary == "Answer [c1]."
    assert block.data.citations[0].docTitle == "Alpha.pdf"


async def test_emits_error_block_when_research_failed():
    state = AgentState(query="x")
    state.agent_results["research"] = AgentResult(
        agent_name="research",
        payload={},
        status="failed",
        error="something exploded",
    )

    agent = UIAgent()
    await agent.run("x", state=state)

    block = state.ui_blocks[0]
    assert block.meta.status == "error"
    assert isinstance(block, CitedSummary)
    assert "something exploded" in block.data.summary


async def test_emits_partial_block_when_research_partial():
    state = AgentState(query="x")
    state.agent_results["research"] = AgentResult(
        agent_name="research",
        payload=_research_payload(),
        status="partial",
        error="no evidence",
    )

    agent = UIAgent()
    await agent.run("x", state=state)
    assert state.ui_blocks[0].meta.status == "partial"


async def test_emits_error_block_when_research_absent():
    """Invariant #6: even with no research result, we MUST emit a block."""
    state = AgentState(query="x")  # no agent_results

    agent = UIAgent()
    await agent.run("x", state=state)
    assert len(state.ui_blocks) == 1
    assert state.ui_blocks[0].meta.status == "error"


async def test_invalid_payload_falls_through_to_error_block():
    """Fail-closed: invariant #2 — never ship a malformed UIBlock."""
    state = AgentState(query="x")
    state.agent_results["research"] = AgentResult(
        agent_name="research",
        payload={"summary": "ok", "segments": "this should be a list", "citations": []},
        status="ok",
    )
    agent = UIAgent()
    await agent.run("x", state=state)
    block = state.ui_blocks[0]
    assert block.meta.status == "error"
    assert isinstance(block, CitedSummary)
    assert "schema validation" in block.data.summary.lower()


# ── Discovery routing ───────────────────────────────────────────────────────

def _gap_analysis_payload() -> dict:
    return {
        "block_type": "GapAnalysis",
        "data": {
            "summary": "Several gaps were found.",
            "gaps": [{"label": "Gap A", "description": "Missing X.", "severity": "high"}],
            "coveredTopics": ["Topic 1"],
        },
    }


async def test_routes_to_gap_analysis_from_discovery():
    from api.genui._generated import GapAnalysis

    state = AgentState(query="x")
    state.agent_results["discovery"] = AgentResult(
        agent_name="discovery",
        payload=_gap_analysis_payload(),
        status="ok",
    )

    agent = UIAgent()
    result = await agent.run("x", state=state)

    assert result.status == "ok"
    block = state.ui_blocks[0]
    assert isinstance(block, GapAnalysis)
    assert block.type == "GapAnalysis"
    assert block.meta.status == "ready"
    assert block.meta.panel == "studio"
    assert block.data.summary == "Several gaps were found."
    assert block.data.gaps[0].severity == "high"


async def test_falls_back_to_cited_summary_when_discovery_absent():
    state = AgentState(query="x")
    state.agent_results["research"] = AgentResult(
        agent_name="research", payload=_research_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("x", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, CitedSummary)


async def test_discovery_invalid_payload_falls_through_to_cited_summary():
    state = AgentState(query="x")
    state.agent_results["discovery"] = AgentResult(
        agent_name="discovery",
        payload={"block_type": "GapAnalysis", "data": {"bad": "field"}},
        status="ok",
    )
    state.agent_results["research"] = AgentResult(
        agent_name="research", payload=_research_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("x", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, CitedSummary), "should fall through to CitedSummary"


# ── Learning routing (Slice 3) ──────────────────────────────────────────────

def _flashcard_payload() -> dict:
    return {
        "block_type": "FlashcardDeck",
        "data": {
            "topic": "Neural Networks",
            "cards": [
                {
                    "front": "What is backprop?",
                    "back": "Gradient computation via chain rule.",
                    "source": _source(),
                    "schedule": None,
                }
            ],
            "totalCards": 1,
            "dueCount": 0,
        },
    }


def _quiz_payload() -> dict:
    return {
        "block_type": "QuizCard",
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


def _feynman_payload() -> dict:
    return {
        "block_type": "FeynmanExplainer",
        "data": {
            "concept": "attention mechanism",
            "explanation": "Like a spotlight on important words.",
            "gaps": ["Omits multi-head attention."],
            "source": _source(),
        },
    }


async def test_routes_flashcard_deck_from_learning():
    state = AgentState(query="make flashcards for neural networks")
    state.agent_results["learning"] = AgentResult(
        agent_name="learning", payload=_flashcard_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("make flashcards", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, FlashcardDeck)
    assert block.type == "FlashcardDeck"
    assert block.meta.status == "ready"
    assert block.meta.panel == "chat"
    assert block.data.topic == "Neural Networks"
    assert len(block.data.cards) == 1


async def test_routes_quiz_card_from_learning():
    state = AgentState(query="quiz me on neural networks")
    state.agent_results["learning"] = AgentResult(
        agent_name="learning", payload=_quiz_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("quiz me", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, QuizCard)
    assert block.type == "QuizCard"
    assert block.data.correctIndex == 0


async def test_routes_feynman_explainer_from_learning():
    state = AgentState(query="feynman explain attention")
    state.agent_results["learning"] = AgentResult(
        agent_name="learning", payload=_feynman_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("feynman explain attention", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, FeynmanExplainer)
    assert block.type == "FeynmanExplainer"
    assert block.data.concept == "attention mechanism"
    assert len(block.data.gaps) == 1


async def test_learning_invalid_payload_falls_through_to_research():
    state = AgentState(query="x")
    state.agent_results["learning"] = AgentResult(
        agent_name="learning",
        payload={"block_type": "FlashcardDeck", "data": {"bad": "field"}},
        status="ok",
    )
    state.agent_results["research"] = AgentResult(
        agent_name="research", payload=_research_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("x", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, CitedSummary), "malformed FlashcardDeck should fall through"


# ── Socratic routing (Slice 3) ──────────────────────────────────────────────

def _socratic_payload() -> dict:
    return {
        "block_type": "SocraticDialog",
        "data": {
            "concept": "backpropagation",
            "turns": [],
            "nextQuestion": "What do you think happens during a forward pass?",
            "bloomLevel": "comprehension",
        },
    }


async def test_routes_socratic_dialog_from_socratic_agent():
    state = AgentState(query="explain backpropagation")
    state.agent_results["socratic"] = AgentResult(
        agent_name="socratic", payload=_socratic_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("explain backpropagation", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, SocraticDialog)
    assert block.type == "SocraticDialog"
    assert block.meta.panel == "chat"
    assert block.data.nextQuestion.endswith("?")


async def test_socratic_invalid_payload_falls_through_to_research():
    state = AgentState(query="x")
    state.agent_results["socratic"] = AgentResult(
        agent_name="socratic",
        payload={"block_type": "SocraticDialog", "data": {"missing_required": True}},
        status="ok",
    )
    state.agent_results["research"] = AgentResult(
        agent_name="research", payload=_research_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("x", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, CitedSummary), "malformed SocraticDialog should fall through"


# ── Writing routing (Slice 4) ───────────────────────────────────────────────

def _draft_payload() -> dict:
    return {
        "block_type": "DraftEditor",
        "data": {
            "title": "Attention in Transformers",
            "sections": [
                {
                    "heading": "Introduction",
                    "body": "Transformers use self-attention [c1].",
                    "citationIds": ["c1"],
                }
            ],
            "citations": [_source()],
            "wordCount": 8,
        },
    }


async def test_routes_draft_editor_from_writing_agent():
    state = AgentState(query="draft a section on attention")
    state.agent_results["writing"] = AgentResult(
        agent_name="writing", payload=_draft_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("draft a section on attention", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, DraftEditor)
    assert block.type == "DraftEditor"
    assert block.meta.status == "ready"
    assert block.meta.panel == "chat"
    assert block.data.title == "Attention in Transformers"
    assert len(block.data.sections) == 1
    assert block.data.wordCount == 8


async def test_writing_llm_error_emits_error_status_block():
    """_error_draft_payload sets _error; UIAgent must emit meta.status='error'."""
    state = AgentState(query="draft something")
    state.agent_results["writing"] = AgentResult(
        agent_name="writing",
        payload={
            "block_type": "DraftEditor",
            "data": {"title": "draft something", "sections": [], "citations": [], "wordCount": 0},
            "_error": "LLM provider down",
        },
        status="ok",
    )

    agent = UIAgent()
    await agent.run("draft something", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, DraftEditor)
    assert block.meta.status == "error", "LLM error payload must render ErrorState"


async def test_writing_invalid_payload_falls_through_to_research():
    state = AgentState(query="x")
    state.agent_results["writing"] = AgentResult(
        agent_name="writing",
        payload={"block_type": "DraftEditor", "data": {"bad": "field"}},
        status="ok",
    )
    state.agent_results["research"] = AgentResult(
        agent_name="research", payload=_research_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("x", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, CitedSummary), "malformed DraftEditor should fall through"


# ── Slice 7 routing ────────────────────────────────────────────────────────────────────────

def _graph_view_payload() -> dict:
    return {
        "block_type": "KnowledgeGraphView",
        "data": {
            "nodes": [
                {"id": "rag", "label": "RAG", "nodeType": "Concept"},
                {"id": "transformer", "label": "Transformer", "nodeType": "Concept"},
            ],
            "edges": [{"source": "rag", "target": "transformer", "relation": "RELATED_TO"}],
            "focusNodeId": "rag",
        },
    }


def _literature_matrix_payload() -> dict:
    return {
        "block_type": "LiteratureMatrix",
        "data": {
            "query": "compare RAG methods",
            "dimensions": ["Methodology", "Dataset"],
            "rows": [
                {
                    "docId": "doc1",
                    "docTitle": "RAG Paper",
                    "cells": [
                        {"text": "Dense retrieval", "citationId": None},
                        {"text": "NQ", "citationId": None},
                    ],
                }
            ],
            "citations": [_source()],
        },
    }


def _contradiction_payload() -> dict:
    return {
        "block_type": "ContradictionAlert",
        "data": {
            "concept": "RAG accuracy",
            "summary": "Sources disagree.",
            "claims": [
                {"docId": "d1", "docTitle": "Paper A", "stance": "helps", "quote": "quote1"},
                {"docId": "d2", "docTitle": "Paper B", "stance": "does not help", "quote": "quote2"},
            ],
        },
    }


def _insight_card_payload() -> dict:
    return {
        "block_type": "InsightCard",
        "data": {
            "insight": "Both assume zero-shot generalisation.",
            "connection": "Shared transferability assumption.",
            "docAId": "doc1",
            "docATitle": "Paper A",
            "docBId": "doc2",
            "docBTitle": "Paper B",
            "citations": [_source()],
        },
    }


async def test_routes_knowledge_graph_view_from_graph_agent():
    from api.genui._generated import KnowledgeGraphView

    state = AgentState(query="show knowledge graph for RAG")
    state.agent_results["graph_agent"] = AgentResult(
        agent_name="graph_agent", payload=_graph_view_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("show knowledge graph", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, KnowledgeGraphView)
    assert block.type == "KnowledgeGraphView"
    assert block.meta.panel == "studio"
    assert block.data.focusNodeId == "rag"
    assert len(block.data.nodes) == 2
    assert len(block.data.edges) == 1


async def test_routes_literature_matrix_from_literature_agent():
    from api.genui._generated import LiteratureMatrix

    state = AgentState(query="compare RAG methods")
    state.agent_results["literature"] = AgentResult(
        agent_name="literature", payload=_literature_matrix_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("compare RAG methods", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, LiteratureMatrix)
    assert block.type == "LiteratureMatrix"
    assert block.meta.panel == "studio"
    assert block.data.dimensions == ["Methodology", "Dataset"]
    assert len(block.data.rows) == 1


async def test_routes_contradiction_alert_from_contradiction_agent():
    from api.genui._generated import ContradictionAlert

    state = AgentState(query="do sources agree on RAG?")
    state.agent_results["contradiction"] = AgentResult(
        agent_name="contradiction", payload=_contradiction_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("do sources agree?", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, ContradictionAlert)
    assert block.type == "ContradictionAlert"
    assert block.meta.panel == "chat"
    assert block.data.concept == "RAG accuracy"
    assert len(block.data.claims) == 2


async def test_routes_insight_card_from_cross_doc_agent():
    from api.genui._generated import InsightCard

    state = AgentState(query="find cross-doc insight")
    state.agent_results["cross_doc"] = AgentResult(
        agent_name="cross_doc", payload=_insight_card_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("find cross-doc insight", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, InsightCard)
    assert block.type == "InsightCard"
    assert block.meta.panel == "chat"
    assert block.data.docAId == "doc1"
    assert block.data.docBId == "doc2"


async def test_routes_insight_card_from_discovery_agent():
    """InsightCard routing from discovery agent is now live (was deferred in Slice 2)."""
    from api.genui._generated import InsightCard

    state = AgentState(query="find insight")
    state.agent_results["discovery"] = AgentResult(
        agent_name="discovery", payload=_insight_card_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("find insight", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, InsightCard)
    assert block.type == "InsightCard"


async def test_comparator_produces_cited_summary():
    state = AgentState(query="compare RAG and RLHF")
    state.agent_results["comparator"] = AgentResult(
        agent_name="comparator",
        payload=_research_payload(summary="RAG vs RLHF comparison."),
        status="ok",
    )

    agent = UIAgent()
    await agent.run("compare", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, CitedSummary)
    assert block.meta.status == "ready"
    assert "comparison" in block.data.summary


async def test_annotation_produces_gap_analysis():
    from api.genui._generated import GapAnalysis

    state = AgentState(query="annotate coverage")
    state.agent_results["annotate"] = AgentResult(
        agent_name="annotate", payload=_gap_analysis_payload(), status="ok"
    )

    agent = UIAgent()
    await agent.run("annotate coverage", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, GapAnalysis)
    assert block.type == "GapAnalysis"
