"""Disk-backed completion cache.

Keyed on the canonical JSON of (provider list signature, model, messages,
system, tools, max_tokens). Reads return the cached `Completion` so
identical requests during development don't burn API spend.

Active in `ENV=local` only — disabled in `study` and `prod-design` so
benchmarks measure real provider latency / cost. The settings-derived
default is set up by `LLMService._default_cache()`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from api.llm.types import Completion


class LLMCache:
    """Two-tier cache: in-process dict + on-disk JSON files."""

    def __init__(self, directory: Path) -> None:
        self._dir = directory
        self._dir.mkdir(parents=True, exist_ok=True)
        self._memory: dict[str, Completion] = {}

    @staticmethod
    def make_key(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _path_for(self, key: str) -> Path:
        # Shard by first 2 hex chars so the directory doesn't accumulate
        # tens of thousands of sibling files.
        return self._dir / key[:2] / f"{key}.json"

    def get(self, key: str) -> Completion | None:
        cached = self._memory.get(key)
        if cached is not None:
            return cached
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            completion = Completion.model_validate(data)
        except (OSError, json.JSONDecodeError, ValueError):
            return None
        self._memory[key] = completion
        return completion

    def put(self, key: str, completion: Completion) -> None:
        self._memory[key] = completion
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(completion.model_dump_json(), encoding="utf-8")
