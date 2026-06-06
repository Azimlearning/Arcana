"""UI Agent - Tier 3. The ONLY agent that picks components (invariant #3).

Routes intent/mode to the most appropriate UIBlock variant (FR-UI-04).
Priority: discovery agent result > research agent result > error block.

Discovery agents signal their desired block type via
`payload["block_type"]` (e.g. "GapAnalysis", "InsightCard") so the UI
Agent can dispatch without knowing the internal shape of each agent.

Slice 1 additions (still in effect):
  - Reads fact_checker result and filters unsupported citations (FR-AGT-09).
  - Downgrades ready -> partial when >50% of citations were dropped.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import ValidationError

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.genui._generated import (
    BlockMeta,
    CitedSummary,
    CitedSummaryData,
    GapAnalysis,
    GapAnalysisData,
    UIBlock,
)

logger = get_logger(__name__)

# Above this fraction of citations dropped, downgrade ready -> partial.
_PARTIAL_DROP_THRESHOLD = 0.5


class UIAgent(BaseAgent):
    name = "ui_agent"
    tier = 3

    async def run(self, query: str, state: AgentState) -> AgentResult:
        block = self._route_to_block(state)
        state.ui_blocks.append(block)
        return AgentResult(
            agent_name=self.name,
            payload={"block_id": block.id, "type": block.type},
            status="ok",
        )

    # -- Routing ---------------------------------------------------------

    def _route_to_block(self, state: AgentState) -> UIBlock:
        """Pick the best UIBlock variant given available agent results.

        Priority order (FR-UI-04):
          1. Discovery agent result (GapAnalysis / InsightCard)
          2. Research agent result (CitedSummary, with Fact Check filter)
          3. Error block (invariant #6: always terminate with a block)
        """
        discovery = state.agent_results.get("discovery")
        if discovery is not None and discovery.status == "ok":
            block = self._build_from_discovery(discovery, order=len(state.ui_blocks))
            if block is not None:
                return block

        research = state.agent_results.get("research")
        fact_check = state.agent_results.get("fact_checker")

        if research is None:
            return self._error_block("Research agent did not run.")
        if research.status == "failed":
            return self._error_block(research.error or "Research agent failed.")

        payload, status = self._apply_fact_check(
            payload=research.payload,
            research_status=research.status,
            fact_check=fact_check,
        )
        try:
            data = CitedSummaryData.model_validate(payload)
            return self._build_cited_summary(data, status=status, order=len(state.ui_blocks))
        except ValidationError as e:
            logger.warning("ui_agent.payload_invalid", error=str(e))
            return self._error_block(
                f"Research payload failed schema validation: {e.error_count()} field(s)"
            )

    def _build_from_discovery(self, result: AgentResult, *, order: int = 0) -> UIBlock | None:
        """Build a GapAnalysis or InsightCard from the discovery agent result.

        Returns None when the payload is missing or fails validation so the
        caller can fall through to the CitedSummary path.
        """
        block_type = result.payload.get("block_type")
        data_dict = result.payload.get("data", {}) or {}

        if block_type == "GapAnalysis":
            try:
                data = GapAnalysisData.model_validate(data_dict)
                return GapAnalysis(
                    type="GapAnalysis",
                    id=_new_block_id(),
                    meta=BlockMeta(panel="studio", order=order, status="ready"),  # type: ignore[arg-type]
                    data=data,
                )
            except ValidationError as e:
                logger.warning("ui_agent.discovery_gap_invalid", error=str(e))
                return None

        # InsightCard routing deferred to Slice 3 (DiscoveryAgent will produce it
        # once cross-doc connection extraction is grounded — see decisions.md).

        return None

    # -- Fact-check filter -----------------------------------------------

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
        filtered["citations"] = [
            c for c in payload.get("citations", []) if c.get("id") not in dropped
        ]
        filtered["segments"] = [
            {
                "text": s.get("text", ""),
                "citationIds": [
                    cid for cid in s.get("citationIds", []) if cid not in dropped
                ],
            }
            for s in payload.get("segments", [])
        ]

        if checked > 0 and (len(dropped) / checked) > _PARTIAL_DROP_THRESHOLD:
            return filtered, "partial"
        return filtered, base_status

    # -- Block constructors ----------------------------------------------

    def _build_cited_summary(self, data: CitedSummaryData, *, status: str, order: int = 0) -> CitedSummary:
        return CitedSummary(
            type="CitedSummary",
            id=_new_block_id(),
            meta=BlockMeta(panel="chat", order=order, status=status),  # type: ignore[arg-type]
            data=data,
        )

    # Keep the old name as an alias so existing test helpers still work.
    _build_block = _build_cited_summary

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
