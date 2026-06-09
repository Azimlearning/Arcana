"""Typed application settings (PRD §9.3 · env guide §1).

Every env var the codebase needs flows through this module. Feature code
must NOT read `os.environ` directly — `.claude/hooks/check_secrets.py`
will flag literals and the no-secret-literals rule blocks the alternative.

`get_settings()` is cached. Tests use the `settings_factory` fixture in
`api/conftest.py` to override env vars and clear the cache.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]   # arcana/
API_DIR = REPO_ROOT / "api"


class Settings(BaseSettings):
    """Typed settings — every value comes from env or a profile file.

    The file pointed at by `env_file` is loaded first; process env then
    overrides on a per-variable basis. Required keys have no default so
    a missing value raises at startup (fail loud).
    """

    model_config = SettingsConfigDict(
        env_file=str(API_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Core / profile ────────────────────────────────────────────
    env: Literal["local", "study", "prod-design"] = "local"
    graph_backend: Literal["networkx", "neo4j"] = "networkx"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # ── LLM primary (Anthropic) — OPTIONAL (skip provider if absent) ──
    anthropic_api_key: SecretStr | None = None
    llm_primary: str = "claude-sonnet"
    llm_primary_max_tokens: int = 4096

    # ── LLM tiers (all via OpenRouter) ──────────────────────────────
    # Heavy: complex synthesis, long-form research, writing
    # Standard: most analysis agents (default fallback)
    # Light: structured extraction, fact-checking, flashcard gen
    openrouter_api_key: SecretStr | None = None
    llm_heavy: str = "anthropic/claude-opus-4.8"
    llm_fallback: str = "anthropic/claude-sonnet-4.6"
    llm_light: str = "anthropic/claude-haiku-4.5"

    # ── Embeddings (OpenAI) — REQUIRED ────────────────────────────
    openai_api_key: SecretStr
    embedding_model: str = "text-embedding-3-large"

    # ── Vector store (Pinecone) — REQUIRED ────────────────────────
    pinecone_api_key: SecretStr
    pinecone_index: str = "arcana"
    pinecone_environment: str = ""

    # ── Knowledge graph (Neo4j) — OPTIONAL ────────────────────────
    neo4j_uri: str = ""
    neo4j_username: str = "neo4j"
    neo4j_password: SecretStr | None = None

    # ── Firebase — P1 (auth stubbable in P0 per env guide §2.6) ───
    firebase_project_id: str = ""
    firebase_client_email: str = ""
    firebase_private_key: SecretStr | None = None

    # ── Academic paper discovery — OPTIONAL ───────────────────────
    semantic_scholar_api_key: SecretStr | None = None

    # ── Retrieval / pipeline tuning ───────────────────────────────
    rrf_k: int = Field(default=60, ge=1, description="RRF constant (§10.4)")
    max_tools_per_prompt: int = Field(default=12, ge=1, description="§11.5 intent-scoping cap")
    hop_budget: int = Field(default=4, ge=1, description="§11.6 max A2A recursion depth")
    token_budget_per_turn: int = Field(default=60000, ge=1, description="R-03 cost guard")

    # ── Object storage ────────────────────────────────────────────
    storage_bucket: str = ""

    # ── Derived helpers ───────────────────────────────────────────
    @property
    def local_storage_path(self) -> Path:
        """Filesystem root for the DocStore slice-time stub.

        Resolution rules (defensive — DocStore writes here, so a runaway
        value must NOT overwrite source files):
          - empty / whitespace-only → `infra/local_storage/`
          - contains `://` (any URI scheme, case-insensitive)
              e.g. `gs://`, `s3://`, `https://` → `infra/local_storage/`
              (those are remote and read by a real DocStore impl in P1)
          - absolute filesystem path → returned as-is (developer's call)
          - relative path → resolved against REPO_ROOT; if traversal
              escapes the repo, fall back to the default
        """
        bucket = (self.storage_bucket or "").strip()
        default = REPO_ROOT / "infra" / "local_storage"
        if not bucket or "://" in bucket.lower():
            return default
        p = Path(bucket).expanduser()
        if p.is_absolute():
            return p
        resolved = (REPO_ROOT / p).resolve()
        try:
            resolved.relative_to(REPO_ROOT)
        except ValueError:
            return default
        return resolved


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor — call this from feature code, never `Settings()` directly."""
    return Settings()  # type: ignore[call-arg]
