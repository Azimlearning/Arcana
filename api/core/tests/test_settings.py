"""Smoke tests for api.core.settings — env loading, defaults, secret wrapping."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from api.core.settings import Settings, get_settings


def test_loads_with_required_keys(settings_factory):
    s = settings_factory()
    assert s.env == "local"
    assert s.graph_backend == "networkx"
    assert s.log_level == "INFO"
    assert s.rrf_k == 60
    assert s.max_tools_per_prompt == 12
    assert s.hop_budget == 4
    assert s.token_budget_per_turn == 60000
    assert s.embedding_model == "text-embedding-3-large"
    assert s.pinecone_index == "arcana"
    assert s.llm_primary == "claude-sonnet"


def test_missing_required_raises(monkeypatch):
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "PINECONE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        # _env_file=None bypasses any developer .env that might satisfy the keys.
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_secret_keys_wrap_with_secretstr(settings_factory):
    s = settings_factory()
    assert isinstance(s.anthropic_api_key, SecretStr)
    assert isinstance(s.openai_api_key, SecretStr)
    assert isinstance(s.pinecone_api_key, SecretStr)
    assert s.anthropic_api_key.get_secret_value() == "test-anthropic"
    # repr() of a SecretStr does NOT leak the value — protects log lines.
    assert "test-anthropic" not in repr(s.anthropic_api_key)


def test_overrides_apply(settings_factory):
    s = settings_factory(rrf_k="42", hop_budget="2")
    assert s.rrf_k == 42
    assert s.hop_budget == 2


def test_local_storage_path_defaults_under_infra(settings_factory):
    s = settings_factory()
    p = s.local_storage_path
    assert p.parts[-2:] == ("infra", "local_storage")


def test_local_storage_path_honors_local_bucket(settings_factory, tmp_path):
    s = settings_factory(storage_bucket=str(tmp_path))
    assert s.local_storage_path == tmp_path


@pytest.mark.parametrize("bucket", [
    "gs://my-bucket",
    "GS://my-bucket",
    "s3://other-bucket",
    "https://example.com/blob",
    "  gs://leading-spaces",
])
def test_local_storage_path_rejects_remote_uris(settings_factory, bucket):
    """Any URI scheme falls through to the default — DocStore must NOT
    write to a Path() of a URI string (would silently land in repo)."""
    s = settings_factory(storage_bucket=bucket)
    assert s.local_storage_path.parts[-2:] == ("infra", "local_storage")


def test_local_storage_path_rejects_repo_traversal(settings_factory):
    """A relative ../ path that resolves outside REPO_ROOT falls back."""
    s = settings_factory(storage_bucket="../../escape")
    assert s.local_storage_path.parts[-2:] == ("infra", "local_storage")


def test_local_storage_path_accepts_safe_relative(settings_factory):
    """A relative path that stays inside REPO_ROOT is resolved against it."""
    s = settings_factory(storage_bucket="infra/test-storage")
    assert s.local_storage_path.parts[-2:] == ("infra", "test-storage")
