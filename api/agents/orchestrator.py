"""Orchestrator - the graph runner (PRD §11.2).

The orchestrator's NODE logic (intent + mode detection) lives as a free
function in `api/agents/graph.py:_orchestrator_node`. This class wraps
the compiled graph and exposes the same `run(query, state) -> AgentResult`
contract the chat route + tests rely on from subsystem 7.

Why split: when the orchestrator runs as a graph node, the node wrapper
would call `agent.run()` - which would recursively try to compile and
invoke the graph again. Keeping the node as a free function and the
class as the runner cleanly separates the two roles."""

from __future__ import annotations

from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent, registry
from api.core.logging import get_logger
from api.llm.types import Message
from api.stores.memory_store import MemoryStore

logger = get_logger(__name__)


class Orchestrator(BaseAgent):
    name = "orchestrator"
    tier = 1

    def __init__(
        self,
        *,
        research: BaseAgent,
        ui_agent: BaseAgent,
        fact_checker: BaseAgent | None = None,
        memory_agent: BaseAgent | None = None,
        memory_store: MemoryStore | None = None,
        extra_agents: list[BaseAgent] | None = None,
    ) -> None:
        self._memory_store = memory_store
        # Register agents that `make_node` will look up. We do NOT
        # register `self`: nothing routes to the orchestrator (it's the
        # entry), and registering would make `route_to_agent("orchestrator",
        # ...)` recurse into the graph.
        registry.register_agent(research)
        registry.register_agent(ui_agent)
        if fact_checker is not None:
            registry.register_agent(fact_checker)
        if memory_agent is not None:
            registry.register_agent(memory_agent)
        for agent in (extra_agents or []):
            registry.register_agent(agent)
        # Late import to avoid base.py <-> graph.py cycle at module load.
        from api.agents.graph import build_graph

        self._graph = build_graph()

    async def run(self, query: str, state: AgentState) -> AgentResult:
        """Compile-and-invoke the StateGraph end-to-end.

        After completion the accumulated fields are copied back into the
        caller's `state` instance so consumers (chat route reads
        `state.ui_blocks`) keep working unchanged from subsystem 7."""
        state.query = query
        logger.info("orchestrator.invoke_graph", query_len=len(query))
        try:
            final: Any = await self._graph.ainvoke(state)
        except Exception:
            logger.exception("orchestrator.graph_failed")
            raise

        # langgraph returns either a Pydantic instance or a dict-like
        # AddableValuesDict depending on version. Handle both.
        if isinstance(final, AgentState):
            for field_name in AgentState.model_fields:
                setattr(state, field_name, getattr(final, field_name))
        elif isinstance(final, dict):
            for k, v in final.items():
                if k in AgentState.model_fields:
                    setattr(state, k, v)

        # Memory writeback: persist the user query + assistant summary
        # so the NEXT turn's Memory Agent can load this exchange. Kept
        # outside the LangGraph state because it touches an external
        # store and shouldn't go through the reducer model.
        await self._persist_turn_to_memory(query=query, state=state)

        logger.info(
            "orchestrator.done",
            ui_blocks=len(state.ui_blocks),
            agents_run=list(state.agent_results.keys()),
        )
        return AgentResult(
            agent_name=self.name,
            payload={
                "blocks_emitted": len(state.ui_blocks),
                "agents_run": list(state.agent_results.keys()),
            },
            status="ok",
        )

    async def astream_run(self, query: str, state: AgentState):
        """Streaming variant of `run` (FR-AGT-07): drive the StateGraph with
        `astream` and yield a per-agent progress event the moment each node's
        result lands, so a long multi-agent turn surfaces incremental
        progress instead of a single end-of-pipeline payload. After the
        stream drains, the final accumulated state is written back into the
        caller's `state` (same contract as `run`) so the route can build the
        trace, fire analytics, and stream the typed blocks.

        Yields dicts: ``{"agent": <name>, "status": "done"}``.
        """
        state.query = query
        logger.info("orchestrator.astream", query_len=len(query))
        seen: set[str] = set()
        final: Any = None
        async for snapshot in self._graph.astream(state, stream_mode="values"):
            final = snapshot
            if isinstance(snapshot, AgentState):
                results = snapshot.agent_results
            elif isinstance(snapshot, dict):
                results = snapshot.get("agent_results", {})
            else:
                results = {}
            for name in results:
                if name not in seen:
                    seen.add(name)
                    yield {"agent": name, "status": "done"}

        if isinstance(final, AgentState):
            for field_name in AgentState.model_fields:
                setattr(state, field_name, getattr(final, field_name))
        elif isinstance(final, dict):
            for k, v in final.items():
                if k in AgentState.model_fields:
                    setattr(state, k, v)

        await self._persist_turn_to_memory(query=query, state=state)
        logger.info(
            "orchestrator.astream_done",
            ui_blocks=len(state.ui_blocks),
            agents_run=list(state.agent_results.keys()),
        )

    async def _persist_turn_to_memory(self, *, query: str, state: AgentState) -> None:
        """Append (user_query, assistant_summary) to the memory store
        for this notebook. Silent no-op when no store is wired.

        Error-block apologies are NOT persisted: next-turn context is
        better served by "user asked X" alone than by "user asked X,
        the system apologized" - the latter biases the model toward
        further apologies."""
        if self._memory_store is None:
            return
        notebook_id = state.notebook_id or "default"
        msgs: list[Message] = [Message(role="user", content=query)]
        if state.ui_blocks:
            block = state.ui_blocks[-1]
            if block.meta.status != "error":
                assistant_text = getattr(block.data, "summary", "") or ""
                if assistant_text:
                    msgs.append(Message(role="assistant", content=assistant_text))
        try:
            await self._memory_store.append_messages(notebook_id, msgs)
        except Exception:
            # Memory persistence must NOT fail the turn that already
            # produced a valid block. Log and move on.
            logger.exception("orchestrator.memory_writeback_failed")
