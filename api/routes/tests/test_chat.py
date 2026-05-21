"""POST /chat - SSE wire format, error envelope, body validation.

Uses FastAPI's TestClient against a minimal in-process app. We skip
`api.main.create_app()` because its lifespan tries to build a real
provider chain (Anthropic, Pinecone, ...) which requires env keys.
"""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.agents.base import AgentResult, AgentState
from api.core.errors import ArcanaError, arcana_error_handler
from api.genui._generated import (
    BlockMeta,
    CitedSummary,
    CitedSummaryData,
    SummarySegment,
)
from api.routes.chat import get_orchestrator
from api.routes.chat import router as chat_router

# ─── Stubs / helpers ──────────────────────────────────────────────


class _StubOrchestrator:
    def __init__(
        self,
        *,
        block: CitedSummary | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._block = block
        self._raise = raise_exc
        self.calls: list[str] = []

    async def run(self, *, query: str, state: AgentState) -> AgentResult:
        self.calls.append(query)
        if self._raise:
            raise self._raise
        if self._block:
            state.ui_blocks.append(self._block)
        return AgentResult(agent_name="orchestrator", payload={})


def _sample_block() -> CitedSummary:
    return CitedSummary(
        type="CitedSummary",
        id="block_test",
        meta=BlockMeta(panel="chat", order=0, status="ready"),
        data=CitedSummaryData(
            summary="answer [c1]",
            segments=[SummarySegment(text="answer", citationIds=["c1"])],
            citations=[],
        ),
    )


def _build_app(orchestrator: object) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(ArcanaError, arcana_error_handler)
    app.include_router(chat_router)
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    return app


def _parse_sse(body: str) -> list[dict]:
    frames: list[dict] = []
    for raw in body.split("\n\n"):
        raw = raw.strip()
        if not raw:
            continue
        f: dict = {}
        for line in raw.split("\n"):
            key, _, value = line.partition(":")
            f[key.strip()] = value.strip()
        if "data" in f:
            f["data"] = json.loads(f["data"])
        frames.append(f)
    return frames


# ─── Happy path ───────────────────────────────────────────────────


def test_chat_streams_one_block():
    orch = _StubOrchestrator(block=_sample_block())
    app = _build_app(orch)
    client = TestClient(app)
    resp = client.post(
        "/chat",
        json={"notebookId": "nb1", "message": "what does my corpus say?", "history": []},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers["x-accel-buffering"] == "no"

    frames = _parse_sse(resp.text)
    events = [f["event"] for f in frames]
    assert events == ["ready", "block", "done"]
    assert frames[1]["data"]["type"] == "CitedSummary"
    assert frames[1]["data"]["id"] == "block_test"
    assert orch.calls == ["what does my corpus say?"]


def test_chat_streams_done_even_with_no_blocks():
    orch = _StubOrchestrator(block=None)
    app = _build_app(orch)
    client = TestClient(app)
    resp = client.post("/chat", json={"notebookId": "nb1", "message": "x", "history": []})
    assert resp.status_code == 200
    frames = _parse_sse(resp.text)
    assert [f["event"] for f in frames] == ["ready", "done"]


# ─── Body validation ─────────────────────────────────────────────


def test_chat_rejects_missing_required_fields():
    orch = _StubOrchestrator(block=None)
    app = _build_app(orch)
    client = TestClient(app)
    resp = client.post("/chat", json={"notebookId": "nb1"})   # missing message + history
    assert resp.status_code == 422


def test_chat_handles_int_in_string_field():
    """Pydantic v2 coerces int → str by default at HTTP boundaries (lax mode).
    Either accept the coercion or 422 — we assert behaviour, not vibes."""
    orch = _StubOrchestrator(block=_sample_block())
    app = _build_app(orch)
    client = TestClient(app)
    resp = client.post(
        "/chat", json={"notebookId": 123, "message": "x", "history": []}
    )
    if resp.status_code == 200:
        # Coercion happened — orchestrator saw the canonical string.
        assert orch.calls == ["x"]
        frames = _parse_sse(resp.text)
        assert any(f["event"] == "done" or f["event"] == "block" for f in frames)
    else:
        # Strict mode rejection — also acceptable (and arguably safer).
        assert resp.status_code == 422
        assert orch.calls == []


def test_chat_emits_error_event_when_orchestrator_raises():
    """Invariant #6 + the wire-layer contract: an uncaught exception inside
    the streaming generator must terminate the SSE with `event: error`,
    not a half-stream with no terminator."""
    orch = _StubOrchestrator(raise_exc=RuntimeError("simulated agent blow-up"))
    app = _build_app(orch)
    client = TestClient(app)
    resp = client.post(
        "/chat", json={"notebookId": "nb1", "message": "x", "history": []}
    )
    assert resp.status_code == 200   # SSE headers already flushed before the raise
    frames = _parse_sse(resp.text)
    events = [f["event"] for f in frames]
    assert "error" in events
    assert events[-1] == "error"   # error is terminal
    assert "done" not in events
    # The error frame should not leak the raw exception string to the client
    # (str(exc) = "simulated agent blow-up"). It carries a generic message
    # plus a request_id for log correlation.
    err_frame = frames[-1]
    assert err_frame["data"]["code"] == "internal_error"
    assert "request_id" in err_frame["data"]
    assert "simulated agent" not in err_frame["data"]["error"]
