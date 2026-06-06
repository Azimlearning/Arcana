"""SocraticAgent — never-answer contract, probing question generation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.agents.base import AgentState
from api.agents.tier2.socratic import SocraticAgent, _is_answer_shaped, _strip_fences

# ── Helpers ────────────────────────────────────────────────────────────────

def _make_agent(llm_text: str = "") -> tuple[SocraticAgent, AsyncMock]:
    llm = MagicMock()
    completion = MagicMock()
    completion.text = llm_text
    llm.complete = AsyncMock(return_value=completion)

    chunk = MagicMock()
    chunk.id = "c1"
    chunk.doc_id = "doc1"
    chunk.page = 2
    chunk.text = "Backpropagation computes gradients via the chain rule."

    vector = MagicMock()
    bm25 = MagicMock()
    graph = MagicMock()
    vector.retrieve = AsyncMock(return_value=[chunk])
    bm25.retrieve = AsyncMock(return_value=[chunk])
    graph.retrieve = AsyncMock(return_value=[])

    agent = SocraticAgent(
        llm_service=llm,
        vector_retriever=vector,
        bm25_retriever=bm25,
        graph_retriever=graph,
    )
    return agent, llm


# ── Unit: _is_answer_shaped ───────────────────────────────────────────────

def test_is_answer_shaped_rejects_statement():
    assert _is_answer_shaped("The answer is backpropagation.") is True


def test_is_answer_shaped_rejects_no_question_mark():
    assert _is_answer_shaped("Tell me about the chain rule") is True


def test_is_answer_shaped_accepts_valid_question():
    assert _is_answer_shaped("What happens when the learning rate is too high?") is False


def test_is_answer_shaped_rejects_therefore():
    assert _is_answer_shaped("Therefore, weights are adjusted?") is True


def test_is_answer_shaped_accepts_probing_question():
    assert _is_answer_shaped("How might you describe the role of each layer in a neural network?") is False


# ── Unit: _strip_fences ───────────────────────────────────────────────────

def test_strip_fences_removes_markdown():
    raw = "```json\n{}\n```"
    assert _strip_fences(raw) == "{}"


# ── Integration: agent.run ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_returns_socratic_dialog_payload():
    llm_json = '{"nextQuestion": "What role does the chain rule play in computing gradients?", "bloomLevel": "comprehension", "reasoning": "..."}'
    agent, _ = _make_agent(llm_json)
    state = AgentState(query="explain backpropagation")
    result = await agent.run("explain backpropagation", state=state)

    assert result.status == "ok"
    assert result.payload["block_type"] == "SocraticDialog"
    data = result.payload["data"]
    assert data["nextQuestion"].endswith("?")
    assert data["bloomLevel"] == "comprehension"


@pytest.mark.asyncio
async def test_run_rejects_answer_shaped_question_and_uses_fallback():
    """When LLM returns an answer-shaped response twice, use safe fallback."""
    llm_json = '{"nextQuestion": "The answer is the chain rule.", "bloomLevel": "recall", "reasoning": ""}'
    agent, llm = _make_agent(llm_json)
    # Both attempts return the same answer-shaped output.
    llm.complete = AsyncMock(return_value=MagicMock(text=llm_json))

    state = AgentState(query="backpropagation")
    result = await agent.run("backpropagation", state=state)

    assert result.status == "ok"
    data = result.payload["data"]
    # Fallback question ends with '?'
    assert data["nextQuestion"].endswith("?")
    # Fallback must NOT be the answer-shaped LLM output
    assert "The answer is" not in data["nextQuestion"]


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

    state = AgentState(query="backpropagation")
    result = await agent.run("backpropagation", state=state)

    # LLM error → fallback question used, still ok status
    assert result.status == "ok"
    assert result.payload["block_type"] == "SocraticDialog"
    assert result.payload["data"]["nextQuestion"].endswith("?")
