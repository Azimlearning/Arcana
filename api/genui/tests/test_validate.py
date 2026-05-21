"""validate_block - happy path, schema drift, fail-closed semantics."""

from __future__ import annotations

import pytest

from api.core.errors import ValidationFailed
from api.genui._generated import (
    BlockMeta,
    CitedSummary,
    CitedSummaryData,
    SummarySegment,
)
from api.genui.validate import validate_block


def _ok_payload() -> dict:
    return {
        "type": "CitedSummary",
        "id": "block_001",
        "meta": {"panel": "chat", "order": 0, "status": "ready"},
        "data": {
            "summary": "answer with [c1]",
            "segments": [{"text": "answer with", "citationIds": ["c1"]}],
            "citations": [
                {
                    "id": "c1",
                    "docId": "doc_a",
                    "docTitle": "Doc A",
                    "page": 4,
                    "quote": "supporting quote",
                }
            ],
        },
    }


def test_valid_dict_passes_through():
    out = validate_block(_ok_payload())
    assert isinstance(out, CitedSummary)
    assert out.id == "block_001"
    assert out.data.summary == "answer with [c1]"


def test_valid_pydantic_instance_revalidated():
    block = CitedSummary(
        type="CitedSummary",
        id="block_002",
        meta=BlockMeta(panel="chat", order=0, status="ready"),
        data=CitedSummaryData(
            summary="hi",
            segments=[SummarySegment(text="hi", citationIds=[])],
            citations=[],
        ),
    )
    out = validate_block(block)
    assert out.id == "block_002"


def test_missing_required_field_raises_validation_failed():
    bad = _ok_payload()
    del bad["meta"]
    with pytest.raises(ValidationFailed) as exc:
        validate_block(bad)
    assert exc.value.code == "validation_failed"
    assert "meta" in str(exc.value.details["errors"])


def test_wrong_discriminator_raises():
    bad = _ok_payload()
    bad["type"] = "FlashcardDeck"   # not in the current union
    with pytest.raises(ValidationFailed):
        validate_block(bad)


def test_invalid_panel_value_raises():
    bad = _ok_payload()
    bad["meta"]["panel"] = "studio_left"   # not a valid Panel literal
    with pytest.raises(ValidationFailed):
        validate_block(bad)


def test_nested_citation_type_mismatch_raises():
    bad = _ok_payload()
    bad["data"]["citations"][0]["page"] = "four"   # str where int expected
    with pytest.raises(ValidationFailed):
        validate_block(bad)


def test_error_envelope_lists_field_paths():
    bad = _ok_payload()
    del bad["meta"]
    del bad["data"]["citations"]
    with pytest.raises(ValidationFailed) as exc:
        validate_block(bad)
    locs = {tuple(e["loc"]) for e in exc.value.details["errors"]}
    # Each missing field should appear in `loc`.
    assert any("meta" in loc for loc in locs)
    assert any("citations" in loc for loc in locs)
