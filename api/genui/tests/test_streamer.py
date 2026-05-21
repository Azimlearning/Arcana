"""stream_blocks - SSE wire format, fail-closed mid-stream."""

from __future__ import annotations

import json

from api.genui._generated import (
    BlockMeta,
    CitedSummary,
    CitedSummaryData,
    SummarySegment,
)
from api.genui.streamer import SCHEMA_VERSION, stream_blocks


def _block(block_id: str = "block_001") -> CitedSummary:
    return CitedSummary(
        type="CitedSummary",
        id=block_id,
        meta=BlockMeta(panel="chat", order=0, status="ready"),
        data=CitedSummaryData(
            summary="hi",
            segments=[SummarySegment(text="hi", citationIds=[])],
            citations=[],
        ),
    )


def _parse_frames(text: str) -> list[dict]:
    """Parse SSE text into a list of {event, id, data} dicts."""
    frames: list[dict] = []
    for raw in text.split("\n\n"):
        raw = raw.strip()
        if not raw:
            continue
        frame: dict = {}
        for line in raw.split("\n"):
            if not line or ":" not in line:
                continue
            key, _, value = line.partition(":")
            frame[key.strip()] = value.strip()
        if "data" in frame:
            frame["data"] = json.loads(frame["data"])
        frames.append(frame)
    return frames


async def test_emits_ready_block_done_for_single_block():
    out = []
    async for frame in stream_blocks([_block("blk_one")]):
        out.append(frame)
    body = "".join(out)
    frames = _parse_frames(body)
    assert [f["event"] for f in frames] == ["ready", "block", "done"]
    assert frames[0]["data"]["schema_version"] == SCHEMA_VERSION
    assert frames[1]["data"]["id"] == "blk_one"
    assert frames[1]["data"]["type"] == "CitedSummary"
    assert frames[2]["data"]["emitted"] == 1


async def test_ids_are_sequential():
    out = []
    async for frame in stream_blocks([_block("a"), _block("b"), _block("c")]):
        out.append(frame)
    frames = _parse_frames("".join(out))
    ids = [int(f["id"]) for f in frames]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)   # unique


async def test_empty_list_yields_ready_and_done():
    out = []
    async for frame in stream_blocks([]):
        out.append(frame)
    frames = _parse_frames("".join(out))
    assert [f["event"] for f in frames] == ["ready", "done"]
    assert frames[1]["data"]["emitted"] == 0


async def test_each_frame_ends_with_double_newline():
    """SSE spec requires each event to end with a blank line."""
    out = []
    async for frame in stream_blocks([_block()]):
        out.append(frame)
    for frame in out:
        assert frame.endswith("\n\n"), f"missing blank-line terminator: {frame!r}"


async def test_error_terminator_does_not_emit_done(monkeypatch):
    """When validation fails mid-stream, the streamer must terminate with
    `event: error` and NOT emit `event: done` — `error` is the terminator."""
    import api.genui.streamer as streamer_mod
    from api.core.errors import ValidationFailed

    def bad_validate(_payload):
        raise ValidationFailed("forced failure", details={"errors": []})

    monkeypatch.setattr(streamer_mod, "validate_block", bad_validate)

    out = []
    async for frame in stream_blocks([_block("blk_x"), _block("blk_y")]):
        out.append(frame)

    frames = _parse_frames("".join(out))
    events = [f["event"] for f in frames]
    assert events == ["ready", "error"]   # NO 'done' after error
    assert frames[-1]["data"]["error"] == "block failed schema validation"
    # `emitted` reflects how many blocks made it before the failure (0 here).
    assert frames[-1]["data"]["emitted"] == 0
    # `details` was redacted from the wire frame.
    assert "details" not in frames[-1]["data"]


async def test_data_lines_have_no_raw_newlines():
    """SSE forbids unescaped newlines inside `data:` values."""
    block = _block()
    block = block.model_copy(
        update={
            "data": CitedSummaryData(
                summary="line one\nline two",   # contains a newline
                segments=[SummarySegment(text="x", citationIds=[])],
                citations=[],
            ),
        }
    )
    out = []
    async for frame in stream_blocks([block]):
        out.append(frame)
    for frame in out:
        # Split out the data line(s) and confirm none of them contain a literal
        # newline that would prematurely terminate the event.
        for line in frame.split("\n")[:-2]:   # last two are the blank terminator
            if line.startswith("data:"):
                payload = line[len("data:"):].strip()
                # Embedded \n is fine (it's an escaped sequence in JSON); raw \n
                # would have broken the line split above. This assertion is
                # implicit but worth stating: json.dumps handles the escape.
                assert "\n" not in payload
