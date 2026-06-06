"""UI Agent — block construction, validation, routing, error paths."""

from __future__ import annotations

from api.agents.base import AgentResult, AgentState
from api.agents.tier3.ui_agent import UIAgent
from api.genui._generated import CitedSummary, FlashcardDeck, QuizCard, SocraticDialog


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
