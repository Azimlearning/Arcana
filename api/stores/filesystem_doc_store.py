"""Filesystem-backed DocStore — the slice-time stub for raw doc + metadata.

Layout under `Settings.local_storage_path`:

    local_storage/
    └── docs/
        ├── {doc_id}.bin     # raw bytes
        └── {doc_id}.json    # DocMetadata serialised

Firestore + Firebase Storage replace this in P1 §1.8. The abstraction
keeps that swap a one-line settings change (per the FR-KG-07 / R-06
pattern applied to documents instead of graph).
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path

from api.stores.doc_store import DocMetadata, DocStore, IngestStatus
from api.stores.errors import DocNotFound, DocStoreError

# Strict allowlist defends against the union of Windows + POSIX path
# pathology: drive-relative paths (C:foo), trailing-dot/space stripping,
# control chars, NTFS-reserved chars (* ? < > | :), and unicode RTL
# overrides. Letters/digits/`_`/`-` only.
_DOC_ID_RE = re.compile(r"[A-Za-z0-9_\-]{1,128}")

# Windows reserved device names — these slip through the regex above
# because they're pure ASCII letters but Win32 routes them to devices.
_WIN_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})


class FilesystemDocStore(DocStore):
    def __init__(self, *, root: Path) -> None:
        self._root = root
        self._docs_dir = root / "docs"
        self._docs_dir.mkdir(parents=True, exist_ok=True)

    async def put(
        self,
        doc_id: str,
        raw: bytes,
        *,
        content_type: str,
        title: str,
        source_uri: str,
        ingest_status: IngestStatus = "pending",
    ) -> DocMetadata:
        _validate(doc_id)
        bin_path = self._bin_path(doc_id)
        meta_path = self._meta_path(doc_id)
        _write_bytes_atomic(bin_path, raw)
        meta = DocMetadata(
            id=doc_id,
            title=title,
            source_uri=source_uri,
            content_type=content_type,
            size_bytes=len(raw),
            ingest_status=ingest_status,
            created_at=datetime.now(UTC),
        )
        _write_text_atomic(meta_path, meta.model_dump_json(indent=2))
        return meta

    async def get_bytes(self, doc_id: str) -> bytes:
        _validate(doc_id)
        path = self._bin_path(doc_id)
        if not path.exists():
            raise DocNotFound(f"no bytes for doc_id={doc_id!r}")
        return path.read_bytes()

    async def get_metadata(self, doc_id: str) -> DocMetadata:
        _validate(doc_id)
        path = self._meta_path(doc_id)
        if not path.exists():
            raise DocNotFound(f"no metadata for doc_id={doc_id!r}")
        try:
            return DocMetadata.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as e:
            raise DocStoreError(f"corrupt metadata for doc_id={doc_id!r}: {e}") from e

    async def update_status(
        self,
        doc_id: str,
        status: IngestStatus,
        *,
        extra_update: dict[str, str] | None = None,
    ) -> DocMetadata:
        meta = await self.get_metadata(doc_id)
        new_extra = {**meta.extra, **(extra_update or {})}
        updated = meta.model_copy(update={"ingest_status": status, "extra": new_extra})
        # Atomic via temp-file + os.replace. Slice-time concurrent writes
        # to the same doc are still undefined (no per-id lock); fine while
        # a single ingestion pipeline owns each document end-to-end.
        _write_text_atomic(self._meta_path(doc_id), updated.model_dump_json(indent=2))
        return updated

    async def list_documents(self) -> list[DocMetadata]:
        out: list[DocMetadata] = []
        for path in sorted(self._docs_dir.glob("*.json")):
            try:
                out.append(DocMetadata.model_validate_json(path.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                # Skip corrupt sidecars rather than crashing the listing.
                continue
        return out

    async def aclose(self) -> None:
        return None

    # ── Internals ─────────────────────────────────────────────────
    def _bin_path(self, doc_id: str) -> Path:
        return self._docs_dir / f"{doc_id}.bin"

    def _meta_path(self, doc_id: str) -> Path:
        return self._docs_dir / f"{doc_id}.json"


def _validate(doc_id: str) -> None:
    if not isinstance(doc_id, str) or not _DOC_ID_RE.fullmatch(doc_id):
        raise DocStoreError(
            f"invalid doc_id: {doc_id!r}. Must match [A-Za-z0-9_-]{{1,128}}."
        )
    if doc_id.upper() in _WIN_RESERVED:
        raise DocStoreError(
            f"invalid doc_id: {doc_id!r}. Reserved Windows device name."
        )


def _write_text_atomic(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _write_bytes_atomic(path: Path, content: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(content)
    os.replace(tmp, path)
