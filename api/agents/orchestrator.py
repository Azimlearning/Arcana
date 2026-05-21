"""Orchestrator — Tier 1, slice-shape.

Real Orchestrator (PRD §11.2) does intent + mode detection, plans a set
of specialist agents, and routes via a LangGraph StateGraph. The slice
defers all of that per the slice ADR — orchestrator → research →
ui_agent runs as a direct async call.

Even at slice scope, this terminates at UI Agent on every path so
invariant #6 (always terminate at UI Agent) is satisfied today.
"""

from __future__ import annotations

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.agents.tier2.research import ResearchAgent
from api.agents.tier3.ui_agent import UIAgent
from api.core.logging import get_logger

logger = get_logger(__name__)


class Orchestrator(BaseAgent):
    name = "orchestrator"
    tier = 1

    def __init__(self, *, research: ResearchAgent, ui_agent: UIAgent) -> None:
        self._research = research
        self._ui = ui_agent

    async def run(self, query: str, state: AgentState) -> AgentResult:
        logger.info("orchestrator.start", query_len=len(query), mode=state.active_mode)

        # Step 1: Research. Writes its result into state.agent_results.
        # We don't react to a failure here — UIAgent will pick up whatever
        # state.agent_results["research"] contains (including a failed
        # status) and emit an appropriate error block (invariant #6).
        await self._research.run(query=query, state=state)

        # Step 2: UI assembly. Always runs.
        ui_result = await self._ui.run(query=query, state=state)

        logger.info(
            "orchestrator.done",
            ui_blocks=len(state.ui_blocks),
            research_status=(
                state.agent_results["research"].status
                if "research" in state.agent_results
                else "absent"
            ),
        )
        return AgentResult(
            agent_name=self.name,
            payload=ui_result.payload,
            status="ok",
        )
