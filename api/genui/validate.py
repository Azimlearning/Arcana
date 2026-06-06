"""Fail-closed UIBlock validator - invariant #2, NFR-SEC-04, R-10.

Every block that leaves the server passes through `validate_block()`.
Any schema violation raises `ValidationFailed`, which the FastAPI handler
maps to a 400 with a structured error envelope - no malformed UIBlock
ever reaches the client.

The validator dispatches via Pydantic's discriminated-union TypeAdapter keyed
on the `type` field. Adding a new UIBlock variant requires no changes here -
the TypeAdapter is rebuilt from `UIBlock` which reflects the full union.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from api.core.errors import ValidationFailed
from api.genui._generated import UIBlock

# Build once at import time — TypeAdapter construction is the expensive step.
_block_adapter = TypeAdapter(UIBlock)


def validate_block(payload: Any) -> UIBlock:
    """Validate an arbitrary payload against the UIBlock discriminated union.

    Accepts either a Pydantic model instance (re-validates for safety via
    model_dump) or a plain dict (typical for agent-produced payloads).
    Raises ValidationFailed on any schema violation.
    """
    if isinstance(payload, BaseModel):
        # Re-validate via model_dump() so a mutated instance can't bypass
        # the check.
        payload_dict = payload.model_dump()
    else:
        payload_dict = payload
    try:
        return _block_adapter.validate_python(payload_dict)
    except ValidationError as e:
        raise ValidationFailed(
            f"UIBlock failed schema validation: {e.error_count()} field(s)",
            details={
                "errors": [
                    {"loc": list(err["loc"]), "msg": err["msg"]} for err in e.errors()
                ],
            },
        ) from e
