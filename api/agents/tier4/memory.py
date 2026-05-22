"""Memory Agent - Tier 4. PRD §12.

Runs FIRST in the LangGraph flow (START -> memory -> orchestrator -> ...).
Loads prior chat history for the active notebook so the Orchestrator can
reason with continuity (FR-AGT-01) and downstream agents see the user's
recent context.

Slice 1: reads from an `InMemoryMemoryStore`. Per-message ordering is
chronological. We cap to `max_history` recent messages to keep the
prompt size bounded (NFR-PERF-01) regardless of corpus age.

Writing back to the store happens in the Orchestrator AFTER the graph
finishes (the agent class wraps `invoke_graph` and persists the final
user/assistant pair). This keeps the Memory Agent itself stateless and
the LangGraph node deltas predictable.
"""

from __future__ import annotations

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.llm.types import Message
from api.stores.memory_store import MemoryStore

logger = get_logger(__name__)


class MemoryAgent(BaseAgent):
    name = "memory"
    tier = 4

    def __init__(self, *, store: MemoryStore, max_history: int = 20) -> None:
        if max_history < 1:
            raise ValueError(f"max_history must be >= 1 (got {max_history})")
        self._store = store
        self._max = max_history

    async def run(self, query: str, state: AgentState) -> AgentResult:
        notebook_id = state.notebook_id or "default"
        history = await self._store.get_messages(notebook_id)
        # Cap to the most recent N - older context is implicitly dropped.
        # P1 will substitute summary-based context window management.
        recent = history[-self._max :] if len(history) > self._max else history

        # Append history + current user query to state.messages. The node
        # wrapper diff's the length so only the new tail appears in the
        # reducer delta - safe across re-invocations.
        state.messages.extend(recent)
        state.messages.append(Message(role="user", content=query))

        logger.info(
            "memory.loaded",
            notebook_id=notebook_id,
            history_loaded=len(recent),
            history_total=len(history),
        )
        return AgentResult(
            agent_name=self.name,
            payload={
                "notebook_id": notebook_id,
                "history_loaded": len(recent),
                "history_total": len(history),
            },
            status="ok",
        )
