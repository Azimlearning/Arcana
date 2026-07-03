"""Minimal async Firestore REST client — no google-cloud-firestore SDK.

Why REST: keeps the request shape explicit (mirrors `pinecone_store.py`
and `api/llm/providers/anthropic.py`), avoids the grpc-heavy SDK, and
makes respx-based unit tests straightforward.

Auth: `ServiceAccountTokenProvider` mints OAuth2 access tokens from the
Firebase service-account credentials already held in `Settings`
(`firebase_client_email` / `firebase_private_key` / `firebase_project_id`).
`google-auth` is the only new dependency; the credential refresh is
blocking, so it runs in a worker thread. Tests inject a stub provider.

Document paths are relative to the database root, e.g.
``users/{uid}/notebooks/{nb_id}``.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

import httpx

from api.stores.errors import StoreError

FIRESTORE_BASE_URL = "https://firestore.googleapis.com/v1"
_DATASTORE_SCOPE = "https://www.googleapis.com/auth/datastore"


class FirestoreError(StoreError):
    code = "firestore_error"


# ── Token providers ───────────────────────────────────────────────────────────


class TokenProvider(Protocol):
    async def token(self) -> str: ...


class ServiceAccountTokenProvider:
    """OAuth2 access tokens from Firebase service-account credentials.

    Wraps `google.oauth2.service_account.Credentials`, refreshing lazily
    when the cached token is missing or expired. Refresh happens in a
    thread because google-auth's transport is blocking.
    """

    def __init__(self, *, project_id: str, client_email: str, private_key: str) -> None:
        if not (project_id and client_email and private_key):
            raise FirestoreError(
                "Firestore backend requires firebase_project_id, "
                "firebase_client_email and firebase_private_key in Settings."
            )
        # Deferred import: google-auth is only needed when Firestore is on.
        from google.oauth2 import service_account

        self._credentials = service_account.Credentials.from_service_account_info(
            {
                "type": "service_account",  # structural field, not a credential  # pragma: allowlist secret
                "project_id": project_id,
                "client_email": client_email,
                # .env files store the key with literal \n escapes.
                "private_key": private_key.replace("\\n", "\n"),
                "token_uri": "https://oauth2.googleapis.com/token",
            },
            scopes=[_DATASTORE_SCOPE],
        )
        self._refresh_lock = asyncio.Lock()

    async def token(self) -> str:
        async with self._refresh_lock:
            if not self._credentials.valid:
                from google.auth.transport.requests import Request

                await asyncio.to_thread(self._credentials.refresh, Request())
            return str(self._credentials.token)


# ── Value codec (Python dict <-> Firestore REST `fields` shape) ──────────────


def to_firestore_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):  # before int — bool subclasses int
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [to_firestore_value(v) for v in value]}}
    if isinstance(value, dict):
        return {"mapValue": {"fields": {k: to_firestore_value(v) for k, v in value.items()}}}
    raise FirestoreError(f"Unsupported Firestore value type: {type(value).__name__}")


def from_firestore_value(value: dict[str, Any]) -> Any:
    if "nullValue" in value:
        return None
    if "booleanValue" in value:
        return bool(value["booleanValue"])
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "stringValue" in value:
        return value["stringValue"]
    if "arrayValue" in value:
        return [from_firestore_value(v) for v in value["arrayValue"].get("values", [])]
    if "mapValue" in value:
        fields = value["mapValue"].get("fields", {})
        return {k: from_firestore_value(v) for k, v in fields.items()}
    if "timestampValue" in value:
        return value["timestampValue"]
    raise FirestoreError(f"Unsupported Firestore value shape: {sorted(value)}")


def encode_fields(data: dict[str, Any]) -> dict[str, Any]:
    return {k: to_firestore_value(v) for k, v in data.items()}


def decode_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {k: from_firestore_value(v) for k, v in fields.items()}


# ── Client ────────────────────────────────────────────────────────────────────


class FirestoreClient:
    """Thin data-plane wrapper: get / set / delete / list on documents."""

    def __init__(
        self,
        *,
        project_id: str,
        token_provider: TokenProvider,
        database: str = "(default)",
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._documents_url = (
            f"{FIRESTORE_BASE_URL}/projects/{project_id}/databases/{database}/documents"
        )
        self._tokens = token_provider
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self._tokens.token()}"}

    async def get(self, path: str) -> dict[str, Any] | None:
        """Return the document's fields as a plain dict, or None if absent."""
        resp = await self._client.get(
            f"{self._documents_url}/{path}", headers=await self._headers()
        )
        if resp.status_code == 404:
            return None
        self._raise_for_status(resp, op="get", path=path)
        return decode_fields(resp.json().get("fields", {}))

    async def set(self, path: str, data: dict[str, Any]) -> None:
        """Create or fully replace the document at *path* (upsert)."""
        resp = await self._client.patch(
            f"{self._documents_url}/{path}",
            headers=await self._headers(),
            json={"fields": encode_fields(data)},
        )
        self._raise_for_status(resp, op="set", path=path)

    async def delete(self, path: str) -> None:
        resp = await self._client.delete(
            f"{self._documents_url}/{path}", headers=await self._headers()
        )
        self._raise_for_status(resp, op="delete", path=path)

    async def list(
        self, collection_path: str, *, page_size: int = 300
    ) -> list[tuple[str, dict[str, Any]]]:
        """Return ``(doc_id, fields)`` for every document in the collection."""
        out: list[tuple[str, dict[str, Any]]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"pageSize": page_size}
            if page_token:
                params["pageToken"] = page_token
            resp = await self._client.get(
                f"{self._documents_url}/{collection_path}",
                headers=await self._headers(),
                params=params,
            )
            self._raise_for_status(resp, op="list", path=collection_path)
            body = resp.json()
            for doc in body.get("documents", []):
                doc_id = doc["name"].rsplit("/", 1)[-1]
                out.append((doc_id, decode_fields(doc.get("fields", {}))))
            page_token = body.get("nextPageToken")
            if not page_token:
                return out

    async def list_collection_ids(self, parent_path: str = "") -> list[str]:
        """Return the ids of sub-collections under *parent_path* ('' = root)."""
        url = self._documents_url + (f"/{parent_path}" if parent_path else "")
        ids: list[str] = []
        page_token: str | None = None
        while True:
            body_json: dict[str, Any] = {"pageSize": 300}
            if page_token:
                body_json["pageToken"] = page_token
            resp = await self._client.post(
                f"{url}:listCollectionIds", headers=await self._headers(), json=body_json
            )
            self._raise_for_status(resp, op="listCollectionIds", path=parent_path)
            body = resp.json()
            ids.extend(body.get("collectionIds", []))
            page_token = body.get("nextPageToken")
            if not page_token:
                return ids

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _raise_for_status(resp: httpx.Response, *, op: str, path: str) -> None:
        if resp.status_code >= 400:
            raise FirestoreError(
                f"Firestore {op} {path!r} failed: {resp.status_code} {resp.text[:200]}"
            )


def firestore_client_from_settings(settings: Any) -> FirestoreClient:
    """Build a FirestoreClient from `Settings` (fail loud on missing creds)."""
    key = settings.firebase_private_key
    return FirestoreClient(
        project_id=settings.firebase_project_id,
        token_provider=ServiceAccountTokenProvider(  # pragma: allowlist secret
            project_id=settings.firebase_project_id,
            client_email=settings.firebase_client_email,
            private_key=key.get_secret_value() if key else "",
        ),
    )
