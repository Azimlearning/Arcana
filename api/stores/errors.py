"""Store-layer exceptions.

`StoreError` is the umbrella; concrete subclasses live next to their
abstraction (`GraphStoreError`, `VectorStoreError`, `DocStoreError`).
Code outside the stores/ layer catches `StoreError` if it doesn't care
which backend failed.
"""

from __future__ import annotations

from api.core.errors import ArcanaError


class StoreError(ArcanaError):
    """Base for graph/vector/doc store failures."""

    code = "store_error"
    http_status = 500


class GraphStoreError(StoreError):
    code = "graph_store_error"


class VectorStoreError(StoreError):
    code = "vector_store_error"


class DocStoreError(StoreError):
    code = "doc_store_error"


class DocNotFound(DocStoreError):
    code = "doc_not_found"
    http_status = 404
