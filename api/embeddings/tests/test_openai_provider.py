"""OpenAI embeddings provider — request shape, response parsing,
dimension enforcement, order-by-index."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from api.embeddings.providers.openai import OPENAI_EMBEDDINGS_URL, OpenAIEmbeddingProvider
from api.embeddings.types import EmbeddingProviderError


def _ok_response(vectors: list[list[float]], *, indices: list[int] | None = None) -> httpx.Response:
    idxs = indices if indices is not None else list(range(len(vectors)))
    return httpx.Response(
        200,
        json={
            "object": "list",
            "data": [
                {"object": "embedding", "embedding": v, "index": i}
                for i, v in zip(idxs, vectors, strict=True)
            ],
            "model": "text-embedding-3-large",
            "usage": {"prompt_tokens": 7, "total_tokens": 7},
        },
    )


@respx.mock
async def test_embed_request_shape():
    route = respx.post(OPENAI_EMBEDDINGS_URL).mock(
        return_value=_ok_response([[0.1] * 3072])
    )
    provider = OpenAIEmbeddingProvider(api_key="sk-openai-test-key")
    try:
        result = await provider.embed(["hello"])
    finally:
        await provider.aclose()

    body = json.loads(route.calls.last.request.content)
    assert body["model"] == "text-embedding-3-large"
    assert body["dimensions"] == 3072
    assert body["input"] == ["hello"]
    headers = route.calls.last.request.headers
    assert headers["Authorization"] == "Bearer sk-openai-test-key"

    assert len(result.vectors) == 1
    assert len(result.vectors[0]) == 3072


@respx.mock
async def test_reorders_by_index():
    # OpenAI guarantees indices, not response array order — provider must sort.
    response = _ok_response(
        vectors=[[1.0] * 3072, [2.0] * 3072, [3.0] * 3072],
        indices=[2, 0, 1],
    )
    respx.post(OPENAI_EMBEDDINGS_URL).mock(return_value=response)
    provider = OpenAIEmbeddingProvider(api_key="sk-openai-test-key")
    try:
        result = await provider.embed(["a", "b", "c"])
    finally:
        await provider.aclose()
    # After sort: index 0 → [2.0...], 1 → [3.0...], 2 → [1.0...]
    assert result.vectors[0][0] == 2.0
    assert result.vectors[1][0] == 3.0
    assert result.vectors[2][0] == 1.0


@respx.mock
async def test_dimension_mismatch_raises():
    respx.post(OPENAI_EMBEDDINGS_URL).mock(
        return_value=_ok_response([[0.1] * 100])  # too short
    )
    provider = OpenAIEmbeddingProvider(api_key="sk-openai-test-key")
    try:
        with pytest.raises(EmbeddingProviderError):
            await provider.embed(["x"])
    finally:
        await provider.aclose()


@respx.mock
async def test_http_error_raises_provider_error():
    respx.post(OPENAI_EMBEDDINGS_URL).mock(return_value=httpx.Response(429, text="rate limit"))
    provider = OpenAIEmbeddingProvider(api_key="sk-openai-test-key")
    try:
        with pytest.raises(EmbeddingProviderError) as exc:
            await provider.embed(["x"])
    finally:
        await provider.aclose()
    assert exc.value.status == 429


async def test_empty_input_short_circuits():
    provider = OpenAIEmbeddingProvider(api_key="sk-openai-test-key")
    try:
        result = await provider.embed([])
    finally:
        await provider.aclose()
    assert result.vectors == []
