"""UI Agent - Tier 3. The ONLY agent that picks components (invariant #3).

Slice 1 additions over the P0 skeleton:
  - Reads `state.agent_results["fact_checker"]` if present and filters
    out citations the Fact Checker flagged as unsupported (FR-AGT-09).
  - Downgrades `meta.status` from "ready" to "partial" when the
    Fact Checker dropped more than half the citations.

Even when Research fails, the agent ALWAYS emits a UIBlock so the graph
terminates at the UI Agent (invariant #6). When the Fact Checker rejects
EVERY citation, we still emit a block - downgraded to "partial" with a
clear summary so the user sees the agent ran but couldn't verify.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import ValidationError

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.genui._generated import BlockMeta, CitedSummary, CitedSummaryData

logger = get_logger(__name__)

# Above this fraction of citations dropped, downgrade ready → partial.
_PARTIAL_DROP_THRESHOLD = 0.5


class UIAgent(BaseAgent):
    name = "ui_agent"
    tier = 3

    async def run(self, query: str, state: AgentState) -> AgentResult:
        research = state.agent_results.get("research")
        fact_check = state.agent_results.get("fact_checker")

        if research is None:
            block = self._error_block("Research agent did not run.")
        elif research.status == "failed":
            block = self._error_block(research.error or "Research agent failed.")
        else:
            payload, status = self._apply_fact_check(
                payload=research.payload,
                research_status=research.status,
                fact_check=fact_check,
            )
            try:
                data = CitedSummaryData.model_validate(payload)
                block = self._build_block(data, status=status)
            except ValidationError as e:
                logger.warning("ui_agent.payload_invalid", error=str(e))
                block = self._error_block(
                    f"Research payload failed schema validation: {e.error_count()} field(s)"
                )

        state.ui_blocks.append(block)
        return AgentResult(
            agent_name=self.name,
            payload={"block_id": block.id, "type": block.type},
            status="ok",
        )

    # ── Fact-check filter ────────────────────────────────────────
    def _apply_fact_check(
        self,
        *,
        payload: dict[str, Any],
        research_status: str,
        fact_check: AgentResult | None,
    ) -> tuple[dict[str, Any], str]:
        """Return (filtered_payload, final_status).

        If the Fact Checker ran with status='ok' and produced a
        `dropped_ids` list, remove those citations from `citations` AND
        from each segment's `citationIds`. Downgrade to 'partial' when
        more than half were dropped.
        """
        base_status = "ready" if research_status == "ok" else "partial"

        if fact_check is None or fact_check.status != "ok":
            return payload, base_status

        dropped = set(fact_check.payload.get("dropped_ids", []) or [])
        checked = int(fact_check.payload.get("checked", 0) or 0)
        if not dropped:
            return payload, base_status

        filtered = dict(payload)
        # Filter citations
        filtered["citations"] = [
            c for c in payload.get("citations", []) if c.get("id") not in dropped
        ]
        # Filter citation references inside segments
        filtered["segments"] = [
            {
                "text": s.get("text", ""),
                "citationIds": [
                    cid for cid in s.get("citationIds", []) if cid not in dropped
                ],
            }
            for s in payload.get("segments", [])
        ]

        # Downgrade if more than half were dropped (FR-AGT-09 threshold).
        if checked > 0 and (len(dropped) / checked) > _PARTIAL_DROP_THRESHOLD:
            return filtered, "partial"
        return filtered, base_status

    # ── Block constructors ───────────────────────────────────────
    def _build_block(self, data: CitedSummaryData, *, status: str) -> CitedSummary:
        return CitedSummary(
            type="CitedSummary",
            id=_new_block_id(),
            meta=BlockMeta(panel="chat", order=0, status=status),  # type: ignore[arg-type]
            data=data,
        )

    def _error_block(self, message: str) -> CitedSummary:
        return CitedSummary(
            type="CitedSummary",
            id=_new_block_id(),
            meta=BlockMeta(panel="chat", order=0, status="error"),
            data=CitedSummaryData(
                summary=f"Sorry — {message}",
                segments=[],
                citations=[],
            ),
        )


def _new_block_id() -> str:
    return f"block_{uuid.uuid4().hex[:12]}"
