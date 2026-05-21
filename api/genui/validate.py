"""Fail-closed UIBlock validator - invariant #2, NFR-SEC-04, R-10.

Every block that leaves the server passes through `validate_block()`.
Any schema violation raises `ValidationFailed`, which the FastAPI handler
maps to a 400 with a structured error envelope - no malformed UIBlock
ever reaches the client.

The validator currently accepts only `CitedSummary` because that's the
single variant the slice's schema declares (`packages/schema/src/blocks.ts`).
When the union grows, this code becomes a tagged-union dispatch keyed on
the `type` discriminator - swap the `model_validate` call below.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from api.core.errors import ValidationFailed
from api.genui._generated import CitedSummary


def validate_block(payload: Any) -> CitedSummary:
    """Validate an arbitrary payload against the UIBlock schema.

    Accepts either a Pydantic instance (re-validates for safety) or a
    plain dict (typical for payloads coming back from agents that built
    them via the typed Pydantic model)."""
    if isinstance(payload, CitedSummary):
        # Re-validate via model_validate(model_dump()) so a mutated
        # instance can't bypass the check.
        payload_dict = payload.model_dump()
    else:
        payload_dict = payload
    try:
        return CitedSummary.model_validate(payload_dict)
    except ValidationError as e:
        raise ValidationFailed(
            f"UIBlock failed schema validation: {e.error_count()} field(s)",
            details={
                "errors": [
                    {"loc": list(err["loc"]), "msg": err["msg"]} for err in e.errors()
                ],
            },
        ) from e
