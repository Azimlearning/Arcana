"""LearningAgent — flashcard/quiz/feynman generation, defensive parsing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.agents.base import AgentState
from api.agents.tier2.learning import (
    LearningAgent,
    _parse_feynman_response,
    _parse_flashcard_response,
    _parse_quiz_response,
    _strip_fences,
)

# ── Helpers ────────────────────────────────────────────────────────────────

def _make_agent(llm_text: str = "") -> tuple[LearningAgent, AsyncMock]:
    llm = MagicMock()
    completion = MagicMock()
    completion.text = llm_text
    llm.complete = AsyncMock(return_value=completion)

    vector = MagicMock()
    bm25 = MagicMock()
    graph = MagicMock()

    chunk = MagicMock()
    chunk.id = "c1"
    chunk.doc_id = "doc1"
    chunk.page = 3
    chunk.text = "Sample text about neural networks."

    vector.retrieve = AsyncMock(return_value=[chunk])
    bm25.retrieve = AsyncMock(return_value=[chunk])
    graph.retrieve = AsyncMock(return_value=[])

    agent = LearningAgent(
        llm_service=llm,
        vector_retriever=vector,
        bm25_retriever=bm25,
        graph_retriever=graph,
    )
    return agent, llm


# ── Unit: _strip_fences ────────────────────────────────────────────────────

def test_strip_fences_removes_json_fence():
    raw = "```json\n{}\n```"
    assert _strip_fences(raw) == "{}"


def test_strip_fences_leaves_plain_json():
    raw = '{"key": "value"}'
    assert _strip_fences(raw) == raw


# ── Unit: _parse_flashcard_response ───────────────────────────────────────

def test_parse_flashcard_happy_path():
    raw = """{
        "topic": "Neural Networks",
        "cards": [
            {
                "front": "What is backpropagation?",
                "back": "Gradient descent through layers.",
                "source": {"id": "c1", "docId": "d1", "docTitle": "NN Book", "page": 5, "quote": "..."}
            }
        ]
    }"""
    result = _parse_flashcard_response(raw, topic="Neural Networks")
    assert result["block_type"] == "FlashcardDeck"
    data = result["data"]
    assert data["topic"] == "Neural Networks"
    assert len(data["cards"]) == 1
    assert data["cards"][0]["front"] == "What is backpropagation?"
    assert data["totalCards"] == 1
    assert data["dueCount"] == 0


def test_parse_flashcard_broken_json_returns_empty_deck():
    result = _parse_flashcard_response("not json at all", topic="Physics")
    assert result["block_type"] == "FlashcardDeck"
    assert result["data"]["cards"] == []
    assert result["data"]["topic"] == "Physics"


def test_parse_flashcard_skips_non_dict_cards():
    raw = '{"cards": ["not a dict", 42, null]}'
    result = _parse_flashcard_response(raw, topic="Test")
    assert result["data"]["cards"] == []


# ── Unit: _parse_quiz_response ────────────────────────────────────────────

def test_parse_quiz_mcq_happy_path():
    raw = """{
        "question": "Which activation function introduces non-linearity?",
        "questionType": "mcq",
        "options": [
            {"index": 0, "text": "Linear"},
            {"index": 1, "text": "ReLU"},
            {"index": 2, "text": "Identity"},
            {"index": 3, "text": "None"}
        ],
        "correctIndex": 1,
        "explanation": "ReLU introduces non-linearity by zeroing negatives.",
        "difficulty": "comprehension",
        "source": {"id": "c1", "docId": "d1", "docTitle": "NN Book", "page": 5, "quote": "..."}
    }"""
    result = _parse_quiz_response(raw, topic="Neural Networks", difficulty="comprehension")
    assert result["block_type"] == "QuizCard"
    data = result["data"]
    assert data["questionType"] == "mcq"
    assert data["correctIndex"] == 1
    assert len(data["options"]) == 4
    assert data["difficulty"] == "comprehension"


def test_parse_quiz_invalid_difficulty_clamped():
    raw = '{"question": "Q?", "questionType": "mcq", "options": [], "correctIndex": null, "explanation": "", "difficulty": "genius", "source": {}}'
    result = _parse_quiz_response(raw, topic="X", difficulty="recall")
    assert result["data"]["difficulty"] == "comprehension"  # default


def test_parse_quiz_broken_json_returns_fallback():
    result = _parse_quiz_response("garbage", topic="Maths", difficulty="recall")
    assert result["block_type"] == "QuizCard"
    assert "Maths" in result["data"]["question"]


# ── Unit: _parse_feynman_response ─────────────────────────────────────────

def test_parse_feynman_happy_path():
    raw = """{
        "concept": "backpropagation",
        "explanation": "Imagine the network is a student correcting mistakes.",
        "gaps": ["Ignores learning rate", "No mention of vanishing gradients"],
        "source": {"id": "c1", "docId": "d1", "docTitle": "DL Book", "page": 4, "quote": "..."}
    }"""
    result = _parse_feynman_response(raw, topic="backpropagation")
    assert result["block_type"] == "FeynmanExplainer"
    data = result["data"]
    assert data["concept"] == "backpropagation"
    assert "student" in data["explanation"]
    assert len(data["gaps"]) == 2
    assert data["source"]["docTitle"] == "DL Book"


def test_parse_feynman_broken_json_returns_empty():
    result = _parse_feynman_response("not json", topic="quantum")
    assert result["block_type"] == "FeynmanExplainer"
    assert result["data"]["concept"] == "quantum"
    assert result["data"]["gaps"] == []


# ── Integration: agent.run ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_returns_flashcard_deck_payload():
    llm_json = '{"topic": "ML", "cards": [{"front": "Q?", "back": "A.", "source": {"id": "c1", "docId": "d1", "docTitle": "T", "page": 1, "quote": "q"}}]}'
    agent, _ = _make_agent(llm_json)
    state = AgentState(query="explain neural networks")
    result = await agent.run("explain neural networks", state=state)

    assert result.status == "ok"
    assert result.payload["block_type"] == "FlashcardDeck"
    assert result.payload["data"]["totalCards"] == 1


@pytest.mark.asyncio
async def test_run_returns_quiz_for_quiz_query():
    llm_json = '{"question": "Q?", "questionType": "mcq", "options": [{"index":0,"text":"A"},{"index":1,"text":"B"},{"index":2,"text":"C"},{"index":3,"text":"D"}], "correctIndex": 0, "explanation": "E.", "difficulty": "recall", "source": {"id":"c1","docId":"d1","docTitle":"T","page":1,"quote":"q"}}'
    agent, _ = _make_agent(llm_json)
    state = AgentState(query="quiz me on backpropagation")
    result = await agent.run("quiz me on backpropagation", state=state)

    assert result.status == "ok"
    assert result.payload["block_type"] == "QuizCard"


@pytest.mark.asyncio
async def test_run_returns_feynman_for_feynman_query():
    llm_json = '{"concept": "attention", "explanation": "Like a spotlight.", "gaps": ["Omits multi-head"], "source": {"id":"c1","docId":"d1","docTitle":"T","page":1,"quote":"q"}}'
    agent, _ = _make_agent(llm_json)
    state = AgentState(query="feynman explain attention mechanism")
    result = await agent.run("feynman explain attention mechanism", state=state)

    assert result.status == "ok"
    assert result.payload["block_type"] == "FeynmanExplainer"
    assert result.payload["data"]["concept"] == "attention"


@pytest.mark.asyncio
async def test_run_fails_gracefully_when_no_chunks():
    agent, _ = _make_agent()
    agent._vector.retrieve = AsyncMock(return_value=[])
    agent._bm25.retrieve = AsyncMock(return_value=[])
    agent._graph.retrieve = AsyncMock(return_value=[])

    state = AgentState(query="x")
    result = await agent.run("x", state=state)

    assert result.status == "failed"
    assert result.error is not None


@pytest.mark.asyncio
async def test_run_fails_gracefully_when_llm_raises():
    agent, llm = _make_agent()
    llm.complete = AsyncMock(side_effect=RuntimeError("LLM down"))

    state = AgentState(query="explain ml")
    result = await agent.run("explain ml", state=state)

    assert result.status == "ok"  # returns error payload, not failed status
    assert result.payload["block_type"] == "FlashcardDeck"
    assert result.payload["data"]["totalCards"] == 0
