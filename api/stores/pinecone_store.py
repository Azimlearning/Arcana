"""Pinecone VectorStore implementation — REST via httpx (no Pinecone SDK).

Why REST: keeps the request shape explicit (mirrors `api/llm/providers/
anthropic.py`), avoids vendoring an SDK whose pickled state could change,
and makes respx-based unit tests straightforward.

Lazy host resolution: serverless Pinecone indexes are reachable at
`https://{host}.pinecone.io`. The host is returned by
`GET https://api.pinecone.io/indexes/{name}`. We cache it after first
resolve. Tests pass `host=` directly to skip the describe call.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from api.stores.errors import VectorStoreError
from api.stores.vector_store import Vector, VectorHit, VectorItem, VectorStore

PINECONE_CONTROL_URL = "https://api.pinecone.io"

# Only accept describe responses pointing at the pinecone.io domain.
# Prevents a compromised/typo'd `host` from redirecting data-plane writes
# to an attacker-controlled URL.
_PINECONE_HOST_RE = re.compile(r"^[A-Za-z0-9.\-]+\.pinecone\.io$")


class PineconeVectorStore(VectorStore):
    """Serverless Pinecone over REST. One instance per index."""

    def __init__(
        self,
        *,
        api_key: str,
        index_name: str,
        dimension: int = 3072,
        host: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._index_name = index_name
        self.dimension = dimension
        self._host = host  # populated on first resolve, or supplied at ctor time
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    # ── Public API ────────────────────────────────────────────────
    async def upsert(self, items: list[VectorItem]) -> None:
        if not items:
            return
        host = await self._ensure_host()
        body = {
            "vectors": [
                {"id": it.id, "values": it.vector, "metadata": it.metadata or {}}
                for it in items
            ]
        }
        await self._post(f"https://{host}/vectors/upsert", body, op="upsert")

    async def query(
        self,
        vector: Vector,
        *,
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        host = await self._ensure_host()
        body: dict[str, Any] = {
            "vector": vector,
            "topK": top_k,
            "includeMetadata": True,
        }
        if filter is not None:
            body["filter"] = filter
        data = await self._post(f"https://{host}/query", body, op="query")
        return [
            VectorHit(id=m["id"], score=float(m.get("score", 0.0)), metadata=m.get("metadata") or {})
            for m in data.get("matches", [])
        ]

    async def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        host = await self._ensure_host()
        await self._post(f"https://{host}/vectors/delete", {"ids": ids}, op="delete")

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def __repr__(self) -> str:
        return (
            f"PineconeVectorStore(index={self._index_name!r}, "
            f"host={self._host or '<unresolved>'}, dimension={self.dimension})"
        )

    # ── Internals ─────────────────────────────────────────────────
    def _headers(self) -> dict[str, str]:
        return {"Api-Key": self._api_key, "content-type": "application/json"}

    async def _ensure_host(self) -> str:
        if self._host:
            return self._host
        url = f"{PINECONE_CONTROL_URL}/indexes/{self._index_name}"
        try:
            resp = await self._client.get(url, headers=self._headers())
        except httpx.HTTPError as e:
            raise VectorStoreError(f"pinecone: network error during describe: {e}") from e
        if resp.status_code >= 400:
            raise VectorStoreError(
                f"pinecone: describe failed HTTP {resp.status_code}: {resp.text[:200]}"
            )
        host = (resp.json() or {}).get("host", "")
        if not host:
            raise VectorStoreError("pinecone: describe response missing 'host'")
        if not _PINECONE_HOST_RE.fullmatch(host):
            raise VectorStoreError(
                f"pinecone: refusing host {host!r}: not a *.pinecone.io address"
            )
        self._host = host
        return host

    async def _post(self, url: str, body: dict[str, Any], *, op: str) -> dict[str, Any]:
        try:
            resp = await self._client.post(url, json=body, headers=self._headers())
        except httpx.HTTPError as e:
            raise VectorStoreError(f"pinecone {op}: network error: {e}") from e
        if resp.status_code >= 400:
            raise VectorStoreError(
                f"pinecone {op}: HTTP {resp.status_code}: {resp.text[:200]}"
            )
        try:
            return resp.json()
        except ValueError:
            return {}
