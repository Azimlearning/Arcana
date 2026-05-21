"""OpenAI embeddings provider.

text-embedding-3-large @ 3072 dimensions — the VERA AI baseline. Keeping
the model + dimensions identical is a methodological requirement for the
graph-vs-flat-RAG benchmark (R-02). Changing either invalidates a
like-for-like comparison.
"""

from __future__ import annotations

import httpx

from api.embeddings.types import EmbeddingProviderError, EmbeddingResult, EmbeddingUsage

OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


class OpenAIEmbeddingProvider:
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-large",
        dimension: int = 3072,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self.dimension = dimension
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(vectors=[], model=self._model, provider=self.name)

        body = {
            "input": texts,
            "model": self._model,
            "dimensions": self.dimension,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }

        try:
            resp = await self._client.post(OPENAI_EMBEDDINGS_URL, json=body, headers=headers)
        except httpx.HTTPError as e:
            raise EmbeddingProviderError(self.name, f"network error: {e}") from e

        if resp.status_code >= 400:
            raise EmbeddingProviderError(
                self.name,
                f"HTTP {resp.status_code}: {resp.text[:200]}",
                status=resp.status_code,
            )

        data = resp.json()
        # Sort by `index` because the API only guarantees the indices, not the order.
        items = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
        vectors: list[list[float]] = [item.get("embedding", []) for item in items]

        # Sanity-check: every vector must have the declared dimension.
        for i, v in enumerate(vectors):
            if len(v) != self.dimension:
                raise EmbeddingProviderError(
                    self.name,
                    f"vector {i} has {len(v)} dims, expected {self.dimension}",
                )

        raw_usage = data.get("usage", {}) or {}
        return EmbeddingResult(
            vectors=vectors,
            model=data.get("model", self._model),
            provider=self.name,
            usage=EmbeddingUsage(
                prompt_tokens=int(raw_usage.get("prompt_tokens", 0)),
                total_tokens=int(raw_usage.get("total_tokens", 0)),
            ),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def __repr__(self) -> str:
        return f"OpenAIEmbeddingProvider(model={self._model!r}, dimension={self.dimension})"
