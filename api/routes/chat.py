"""POST /chat - the slice's only public route. PRD §10.1 Listing 10.1.

Lifecycle of one turn:
  1. Validate the incoming `ChatRequest` (Pydantic does this automatically).
  2. Build an `AgentState` from the request.
  3. Run the orchestrator - which routes Research → UI Agent and appends
     the resulting UIBlock to `state.ui_blocks`.
  4. Stream `state.ui_blocks` to the client over SSE.
  5. Fire a `TurnEvent` to the EventStore (fire-and-forget, FR-ANL-01).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.agents.base import AgentState
from api.agents.orchestrator import Orchestrator
from api.core.auth import CurrentUser, get_current_user
from api.core.logging import bind_request_context, clear_request_context, get_logger
from api.genui._generated import ChatRequest
from api.genui.streamer import SCHEMA_VERSION, format_sse_event, stream_blocks
from api.genui.trace import build_trace

logger = get_logger(__name__)

router = APIRouter()


def get_orchestrator() -> Orchestrator:
    """Dependency placeholder - the FastAPI app's lifespan overrides this
    with a real orchestrator built from `Settings`. Tests override with a
    stub. If neither happens, requests fail fast with a 503."""
    raise HTTPException(
        status_code=503,
        detail=(
            "Orchestrator dependency not configured. "
            "api.main.create_app() wires this at startup; tests must override."
        ),
    )


@router.post("/chat")
async def chat(
    body: ChatRequest,
    http_request: Request,
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> StreamingResponse:
    state = AgentState(
        query=body.message,
        notebook_id=body.notebookId,
        user_id=user.uid,   # FR-KG-02: threads user identity through the agent graph
        # A missing mode coalesces to the safe default; the orchestrator
        # maps active_mode → intent (graph.py:_MODE_TO_INTENT). FR-UI-06.
        active_mode=body.activeMode or "research",
        retrieval_mode=body.retrievalMode or "auto",  # FR-RET-07
    )

    async def gen() -> AsyncIterator[str]:
        request_id = uuid.uuid4().hex[:12]
        bind_request_context(request_id=request_id)
        logger.info(
            "chat.start",
            request_id=request_id,
            message_len=len(body.message),
            mode=state.active_mode,
        )
        try:
            try:
                t0 = time.perf_counter()

                # FR-AGT-07: stream partial progress while the multi-agent graph
                # runs, so long turns surface activity instead of a silent wait.
                # `ready` is emitted up front; each completed node yields a
                # `progress` frame; the typed blocks + trace + done follow.
                seq = 0
                yield format_sse_event("ready", seq, {"schema_version": SCHEMA_VERSION})
                async for prog in orchestrator.astream_run(query=body.message, state=state):
                    seq += 1
                    yield format_sse_event("progress", seq, prog)

                latency_ms = (time.perf_counter() - t0) * 1000
                _fire_turn_event(http_request, user, request_id, state, latency_ms)

                trace_payload = build_trace(state)
                async for frame in stream_blocks(
                    state.ui_blocks,
                    trace=trace_payload,
                    emit_ready=False,
                    start_seq=seq + 1,
                ):
                    yield frame
                logger.info(
                    "chat.done",
                    request_id=request_id,
                    blocks=len(state.ui_blocks),
                )
            except Exception:
                logger.exception("chat.unhandled", request_id=request_id)
                yield format_sse_event(
                    "error",
                    0,
                    {
                        "error": "internal error during chat turn",
                        "code": "internal_error",
                        "request_id": request_id,
                    },
                )
        finally:
            clear_request_context()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


_DEFAULT_SUGGESTIONS = [
    "What are the main themes across my documents?",
    "Compare and contrast the key arguments in my sources.",
    "What gaps or contradictions exist in my corpus?",
]


@router.get("/suggestions")
async def get_suggestions(
    http_request: Request,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Return 3 suggested cross-document questions for the empty-chat state.

    Uses the light LLM tier (haiku) with doc titles for fast, relevant
    suggestions. Falls back to generic questions on failure or if no docs.
    """
    shared = getattr(http_request.app.state, "shared", {})
    doc_store = shared.get("doc_store")
    llm = shared.get("llm_light")

    if doc_store is None:
        return {"suggestions": _DEFAULT_SUGGESTIONS}

    try:
        all_docs = await doc_store.list_documents()
    except Exception:
        return {"suggestions": _DEFAULT_SUGGESTIONS}

    ready = [d for d in all_docs if d.ingest_status == "ready"]
    if not ready:
        return {"suggestions": _DEFAULT_SUGGESTIONS}

    titles = [d.title for d in ready[:6]]

    if llm is None:
        return {"suggestions": _fallback_suggestions(titles)}

    try:
        from api.llm.types import Message

        titles_str = "\n".join(f"- {t}" for t in titles)
        prompt = (
            f"A researcher has these documents in their knowledge base:\n{titles_str}\n\n"
            "Generate exactly 3 short, specific, cross-document research questions "
            "they could ask about this corpus. Each question should require comparing "
            "or connecting ideas across at least two documents. "
            "Output ONLY the 3 questions, one per line, no numbering, no markdown."
        )
        completion = await llm.complete(
            messages=[Message(role="user", content=prompt)],
            max_tokens=200,
        )
        lines = [ln.strip() for ln in completion.text.strip().splitlines() if ln.strip()]
        questions = lines[:3] if len(lines) >= 3 else lines
        # Pad with defaults if LLM returned fewer than 3
        while len(questions) < 3:
            questions.append(_DEFAULT_SUGGESTIONS[len(questions)])
        return {"suggestions": questions}
    except Exception:
        return {"suggestions": _fallback_suggestions(titles)}


def _fallback_suggestions(titles: list[str]) -> list[str]:
    if len(titles) >= 2:
        return [
            f"What are the key differences between {titles[0]!r} and {titles[1]!r}?",
            "What common themes appear across my documents?",
            "What contradictions or disagreements exist in my corpus?",
        ]
    return _DEFAULT_SUGGESTIONS


def _fire_turn_event(
    http_request: Request,
    user: CurrentUser,
    request_id: str,
    state: AgentState,
    latency_ms: float,
) -> None:
    """Schedule turn event capture as a fire-and-forget task.

    Swallows all errors so analytics failures never interrupt chat.
    """
    try:
        shared = getattr(http_request.app.state, "shared", {})
        event_store = shared.get("event_store")
        if event_store is None:
            return

        from api.analytics.event_store import TurnEvent

        event = TurnEvent(
            session_id=request_id,
            user_id=user.uid,
            timestamp=datetime.now(UTC).isoformat(),
            query=state.query[:500],
            mode=state.active_mode,
            intent=state.intent,
            agents_triggered=list(state.intermediate_results.keys()),
            latency_ms=round(latency_ms, 1),
            block_types=[b.kind for b in state.ui_blocks],
            retrieved_chunk_count=len(state.retrieved_ctx),
        )
        asyncio.create_task(event_store.append_turn(event))  # noqa: RUF006
    except Exception:
        logger.exception("chat.turn_event_failed")
