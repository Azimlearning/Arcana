"""Server-Sent Events streamer for UIBlocks - PRD §13.2.

Wire format (W3C EventSource spec compliant):

    event: ready
    id: 0
    data: {"schema_version":1}

    event: block
    id: 1
    data: {"type":"CitedSummary","id":"block_...","meta":{...},"data":{...}}

    event: done
    id: 2
    data: {"emitted":1}

Why this shape (production rationale):
  - Standard SSE: `event:` field dispatches to `addEventListener("block",...)`
    on browsers' native EventSource - no custom parser needed.
  - `id:` enables client reconnect/replay via `Last-Event-Id` header (a
    P1 feature, but the field is here from day one so we don't break
    older clients when we add it).
  - JSON-per-event envelope: forward-compatible - new fields land inside
    the data object without changing the protocol.
  - Single-line JSON (`separators=(",", ":")`): SSE forbids raw newlines
    in `data:` values, and `json.dumps` with these separators emits a
    single line by default.

Terminator contract: a stream ALWAYS ends with exactly one of `done`
(success) or `error` (failure). Clients treat either as terminal; do
NOT emit a `done` after an `error`. The route handler in
`api/routes/chat.py` follows the same contract for out-of-band errors
that fire before `stream_blocks` runs.

Validation runs on every block egress (invariant #2, fail-closed).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from api.core.errors import ValidationFailed
from api.core.logging import get_logger
from api.genui._generated import UIBlock
from api.genui.validate import validate_block

logger = get_logger(__name__)

SCHEMA_VERSION = 1


def format_sse_event(event: str, seq: int, data: dict[str, Any]) -> str:
    """Serialize a single SSE frame. Public so the route handler can emit
    out-of-band error frames (e.g., when orchestrator.run() raises before
    stream_blocks even starts)."""
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return f"event: {event}\nid: {seq}\ndata: {payload}\n\n"


async def stream_blocks(
    blocks: list[UIBlock],
    *,
    trace: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    """Yield SSE frames for each block, framed by `ready` and `done` events.

    If `trace` is supplied, emits `event: trace` immediately after `ready` so
    the frontend renders the agent pipeline strip before any block arrives.

    On a validation failure mid-stream, emits a final `event: error` and
    terminates - the client sees an explicit failure rather than a
    silently truncated stream.
    """
    seq = 0
    yield format_sse_event("ready", seq, {"schema_version": SCHEMA_VERSION})
    if trace is not None:
        seq += 1
        yield format_sse_event("trace", seq, trace)

    emitted = 0
    for block in blocks:
        seq += 1
        try:
            validated = validate_block(block)
        except ValidationFailed as e:
            logger.warning(
                "streamer.invalid_block",
                block_id=getattr(block, "id", "<unknown>"),
                error=str(e),
            )
            seq += 1
            yield format_sse_event(
                "error",
                seq,
                {
                    "error": "block failed schema validation",
                    "block_id": getattr(block, "id", "<unknown>"),
                    "code": e.code,
                    "emitted": emitted,
                    # NOTE: `details` intentionally omitted from the wire — it
                    # contains internal field paths that aid the server log
                    # but should not surface to the client.
                },
            )
            return   # `error` is terminal — do NOT emit `done` after.
        yield format_sse_event("block", seq, validated.model_dump())
        emitted += 1

    seq += 1
    yield format_sse_event("done", seq, {"emitted": emitted})
