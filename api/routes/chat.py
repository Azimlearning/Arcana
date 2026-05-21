"""POST /chat - the slice's only public route. PRD §10.1 Listing 10.1.

Lifecycle of one turn:
  1. Validate the incoming `ChatRequest` (Pydantic does this automatically).
  2. Build an `AgentState` from the request.
  3. Run the orchestrator - which routes Research → UI Agent and appends
     the resulting UIBlock to `state.ui_blocks`.
  4. Stream `state.ui_blocks` to the client over SSE.

Auth is intentionally absent for the slice (P0 shortcut per env guide §2.6).
Firebase token verification lands in P1 §1.8.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.agents.base import AgentState
from api.agents.orchestrator import Orchestrator
from api.core.logging import bind_request_context, clear_request_context, get_logger
from api.genui._generated import ChatRequest
from api.genui.streamer import format_sse_event, stream_blocks

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
    request: ChatRequest,
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
) -> StreamingResponse:
    state = AgentState(
        query=request.message,
        notebook_id=request.notebookId,
    )

    async def gen() -> AsyncIterator[str]:
        request_id = uuid.uuid4().hex[:12]
        # `bind_request_context` writes to a structlog contextvar that
        # propagates into nested awaited calls in the same task — every
        # agent / retriever / store call below this point gets `request_id`
        # in its log lines. Subsequent calls in this turn should pass
        # `agent=...` only; the same `request_id` is already bound.
        bind_request_context(request_id=request_id)
        logger.info(
            "chat.start", request_id=request_id, message_len=len(request.message)
        )
        try:
            try:
                await orchestrator.run(query=request.message, state=state)
                async for frame in stream_blocks(state.ui_blocks):
                    yield frame
                logger.info(
                    "chat.done",
                    request_id=request_id,
                    blocks=len(state.ui_blocks),
                )
            except Exception:
                # Headers are already flushed by `StreamingResponse`, so
                # FastAPI's exception handler cannot run. Invariant #6
                # ("always terminate") requires we close with a sentinel
                # frame ourselves. `error` is terminal; no `done` after.
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
            # SSE-specific headers - keep proxies from buffering or caching
            # mid-stream content. `X-Accel-Buffering: no` disables Nginx
            # buffering specifically.
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
