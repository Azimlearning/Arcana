"""UI Agent — Tier 3. The ONLY agent that picks components (invariant #3).

Slice scope: the catalog has one variant (`CitedSummary`), so component
selection is trivial. The agent's real job in the slice is:
  1. Read `state.agent_results["research"]`.
  2. Validate the dict payload against the generated `CitedSummaryData`
     Pydantic model (fail-closed before SSE — invariant #2 / NFR-SEC-04).
  3. Construct a `CitedSummary` UIBlock with a fresh id + `BlockMeta`.
  4. Append it to `state.ui_blocks` and return.

Even when Research fails, this agent ALWAYS emits a UIBlock so the
graph terminates at the UI Agent (invariant #6).
"""

from __future__ import annotations

import uuid

from pydantic import ValidationError

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.genui._generated import BlockMeta, CitedSummary, CitedSummaryData

logger = get_logger(__name__)


class UIAgent(BaseAgent):
    name = "ui_agent"
    tier = 3

    async def run(self, query: str, state: AgentState) -> AgentResult:
        research = state.agent_results.get("research")
        if research is None:
            block = self._error_block("Research agent did not run.")
        elif research.status == "failed":
            block = self._error_block(research.error or "Research agent failed.")
        else:
            try:
                data = CitedSummaryData.model_validate(research.payload)
                status = "ready" if research.status == "ok" else "partial"
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

    # ── Block constructors ────────────────────────────────────────
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
