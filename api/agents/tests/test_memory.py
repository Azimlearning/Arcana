"""Memory Agent + InMemoryMemoryStore + cross-turn continuity."""

from __future__ import annotations

import pytest

from api.agents.base import AgentState, registry
from api.agents.tier4.memory import MemoryAgent
from api.llm.types import Message
from api.stores.in_memory_store import InMemoryMemoryStore


@pytest.fixture(autouse=True)
def clean_registry():
    registry.reset()
    yield
    registry.reset()


# ── MemoryStore ──────────────────────────────────────────────────


async def test_in_memory_store_isolates_notebooks():
    store = InMemoryMemoryStore()
    await store.append_messages("nb1", [Message(role="user", content="hi from 1")])
    await store.append_messages("nb2", [Message(role="user", content="hi from 2")])
    assert (await store.get_messages("nb1"))[0].content == "hi from 1"
    assert (await store.get_messages("nb2"))[0].content == "hi from 2"


async def test_in_memory_store_appends_in_order():
    store = InMemoryMemoryStore()
    await store.append_messages("nb1", [
        Message(role="user", content="a"),
        Message(role="assistant", content="b"),
    ])
    await store.append_messages("nb1", [Message(role="user", content="c")])
    msgs = await store.get_messages("nb1")
    assert [m.content for m in msgs] == ["a", "b", "c"]


async def test_in_memory_store_clear_drops_notebook():
    store = InMemoryMemoryStore()
    await store.append_messages("nb1", [Message(role="user", content="x")])
    await store.clear("nb1")
    assert await store.get_messages("nb1") == []


async def test_in_memory_store_empty_append_noop():
    store = InMemoryMemoryStore()
    await store.append_messages("nb1", [])
    assert await store.get_messages("nb1") == []


# ── MemoryAgent ──────────────────────────────────────────────────


async def test_memory_agent_loads_history_into_state():
    store = InMemoryMemoryStore()
    await store.append_messages("nb1", [
        Message(role="user", content="prev question"),
        Message(role="assistant", content="prev answer"),
    ])
    agent = MemoryAgent(store=store)
    state = AgentState(query="new question", notebook_id="nb1")
    result = await agent.run("new question", state=state)

    # Prior history + the current user query.
    contents = [m.content for m in state.messages]
    assert contents == ["prev question", "prev answer", "new question"]
    assert result.payload["history_loaded"] == 2


async def test_memory_agent_empty_notebook_just_appends_query():
    store = InMemoryMemoryStore()
    agent = MemoryAgent(store=store)
    state = AgentState(query="first ever question", notebook_id="brand_new")
    await agent.run("first ever question", state=state)
    assert [m.content for m in state.messages] == ["first ever question"]


async def test_memory_agent_caps_history_at_max():
    store = InMemoryMemoryStore()
    # Stash 30 messages; agent should cap to 5.
    await store.append_messages("nb1", [
        Message(role="user", content=f"msg-{i}") for i in range(30)
    ])
    agent = MemoryAgent(store=store, max_history=5)
    state = AgentState(query="now", notebook_id="nb1")
    await agent.run("now", state=state)
    contents = [m.content for m in state.messages]
    # Should be last 5 of msg-25..msg-29, then "now".
    assert contents == ["msg-25", "msg-26", "msg-27", "msg-28", "msg-29", "now"]


async def test_memory_agent_default_notebook_when_state_unset():
    store = InMemoryMemoryStore()
    await store.append_messages("default", [Message(role="user", content="earlier")])
    agent = MemoryAgent(store=store)
    state = AgentState(query="now")  # no notebook_id
    result = await agent.run("now", state=state)
    assert result.payload["notebook_id"] == "default"
    assert state.messages[0].content == "earlier"


def test_memory_agent_rejects_invalid_max_history():
    with pytest.raises(ValueError):
        MemoryAgent(store=InMemoryMemoryStore(), max_history=0)
