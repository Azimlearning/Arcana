"""Tests for UserGraphRegistry (FR-KG-02)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.stores.networkx_store import NetworkXGraphStore
from api.stores.user_graph_registry import UserGraphRegistry
from api.stores.graph_store import GraphNode


@pytest.fixture
def registry(tmp_path: Path) -> UserGraphRegistry:
    return UserGraphRegistry(root=tmp_path / "graphs")


@pytest.mark.asyncio
async def test_get_or_create_returns_store(registry: UserGraphRegistry) -> None:
    store = await registry.get_or_create("user-a")
    assert isinstance(store, NetworkXGraphStore)


@pytest.mark.asyncio
async def test_get_or_create_same_instance(registry: UserGraphRegistry) -> None:
    s1 = await registry.get_or_create("user-a")
    s2 = await registry.get_or_create("user-a")
    assert s1 is s2


@pytest.mark.asyncio
async def test_different_users_get_different_stores(registry: UserGraphRegistry) -> None:
    sa = await registry.get_or_create("user-a")
    sb = await registry.get_or_create("user-b")
    assert sa is not sb


@pytest.mark.asyncio
async def test_get_if_loaded_returns_none_before_access(registry: UserGraphRegistry) -> None:
    assert registry.get_if_loaded("user-z") is None


@pytest.mark.asyncio
async def test_get_if_loaded_returns_store_after_access(registry: UserGraphRegistry) -> None:
    await registry.get_or_create("user-a")
    assert registry.get_if_loaded("user-a") is not None


@pytest.mark.asyncio
async def test_save_persists_to_disk(registry: UserGraphRegistry, tmp_path: Path) -> None:
    store = await registry.get_or_create("user-a")
    await store.upsert_node(GraphNode(id="n1", type="Concept", label="Test"))
    await registry.save("user-a")

    graph_file = tmp_path / "graphs" / "user-a.json"
    assert graph_file.exists()
    data = json.loads(graph_file.read_text())
    node_ids = [n["id"] for n in data.get("nodes", [])]
    assert "n1" in node_ids


@pytest.mark.asyncio
async def test_save_noop_for_unloaded_user(registry: UserGraphRegistry) -> None:
    # Should not raise even if user has never accessed the registry.
    await registry.save("ghost-user")


@pytest.mark.asyncio
async def test_save_all_flushes_all_users(registry: UserGraphRegistry, tmp_path: Path) -> None:
    for uid in ("alice", "bob"):
        store = await registry.get_or_create(uid)
        await store.upsert_node(GraphNode(id=f"n-{uid}", type="Concept", label=uid))
    await registry.save_all()

    for uid in ("alice", "bob"):
        path = tmp_path / "graphs" / f"{uid}.json"
        assert path.exists(), f"graph for {uid} not persisted"


@pytest.mark.asyncio
async def test_reload_from_disk(tmp_path: Path) -> None:
    """A new registry instance loads an existing graph from disk."""
    reg1 = UserGraphRegistry(root=tmp_path / "graphs")
    store1 = await reg1.get_or_create("user-a")
    await store1.upsert_node(GraphNode(id="concept-x", type="Concept", label="X"))
    await reg1.save("user-a")

    # New registry instance — simulates server restart.
    reg2 = UserGraphRegistry(root=tmp_path / "graphs")
    store2 = await reg2.get_or_create("user-a")
    node = await store2.get_node("concept-x")
    assert node is not None
    assert node.label == "X"
