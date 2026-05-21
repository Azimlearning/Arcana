#!/usr/bin/env python3
"""
Arcana — post-write formatter & light check (PostToolUse on Write/Edit/MultiEdit).

After a file is written, format it in place and run a quick lint/type check.
Failures are reported on stderr with exit code 2 so the model can see them
and fix in the next turn — but the file write itself stands.

Tools used (skipped silently if not installed):
  Python  — ruff format, ruff check --fix, pyright
  TS/JS   — prettier --write
  Markdown / CSS / JSON — prettier --write

Authority: .claude/rules/dependency-direction.md (consistent style across the layer).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: str) -> tuple[int, str]:
    if not shutil.which(cmd[0]):
        return 0, ""  # tool not installed → skip
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=45, check=False
        )
    except subprocess.TimeoutExpired:
        return 1, f"{cmd[0]}: timed out"
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def main() -> int:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return 0

    tool = data.get("tool_name", "")
    if tool not in {"Write", "Edit", "MultiEdit"}:
        return 0

    file_path = (data.get("tool_input") or {}).get("file_path", "")
    if not file_path or not Path(file_path).is_file():
        return 0

    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or "."
    suffix = Path(file_path).suffix
    report: list[str] = []

    def section(label: str, code: int, out: str) -> None:
        if code != 0 and out:
            report.append(f"--- {label} ---\n{out}\n")

    if suffix == ".py":
        section("ruff format", *run(["ruff", "format", file_path], cwd))
        section("ruff check", *run(["ruff", "check", "--fix", file_path], cwd))
        section("pyright",    *run(["pyright", file_path], cwd))
    elif suffix in {".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".css", ".scss"}:
        section("prettier", *run(["prettier", "--write", file_path], cwd))

    if not report:
        return 0

    msg = [f"ℹ️  Post-write checks reported issues in {file_path} — fix in the next turn:", ""]
    msg.extend(report)
    print("\n".join(msg), file=sys.stderr)
    return 2  # exit 2 so the model sees stderr and self-corrects


if __name__ == "__main__":
    sys.exit(main())
