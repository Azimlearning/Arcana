"""POST /highlights — fold a user highlight/note back into the graph (FR-USR-05).

A reader's own highlights and margin notes are first-class knowledge: this
route runs the same entity extraction used for documents over the highlighted
text and merges the result into the calling user's per-user graph, attributed
to the source document. NFR-SEC-01: guarded by get_current_user.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from api.core.auth import CurrentUser, get_current_user
from api.core.logging import get_logger
from api.genui._generated import HighlightRequest, HighlightResponse
from api.ingestion.pipeline import ingest_highlight

logger = get_logger(__name__)

router = APIRouter(tags=["graph"])


@router.post("/highlights", response_model=HighlightResponse)
async def create_highlight(
    body: HighlightRequest,
    http_request: Request,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> HighlightResponse:
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text must not be empty.")
    if not (body.docId or "").strip():
        raise HTTPException(status_code=422, detail="docId is required.")

    # The note (if any) is appended so both the highlighted passage and the
    # reader's own commentary contribute concepts to the graph.
    combined = text if not body.note else f"{text}\n\n{body.note.strip()}"

    shared = getattr(http_request.app.state, "shared", {})
    llm = shared.get("llm")
    graph_registry = shared.get("graph_registry")
    if llm is None or graph_registry is None:
        raise HTTPException(status_code=503, detail="Graph ingestion is not available.")

    graph = await graph_registry.get_or_create(user.uid)
    try:
        result = await ingest_highlight(
            text=combined, doc_id=body.docId, graph=graph, llm=llm
        )
        await graph_registry.save(user.uid)
    except Exception as exc:
        logger.exception("highlight.failed", doc_id=body.docId)
        raise HTTPException(status_code=500, detail=f"Highlight ingestion failed: {exc}") from exc

    logger.info("highlight.ingested", user_id=user.uid, doc_id=body.docId, **{
        k: v for k, v in result.items() if k != "concepts"
    })
    return HighlightResponse(
        docId=body.docId,
        nodesAdded=result["nodes"],
        edgesAdded=result["edges"],
        concepts=result["concepts"],
    )
