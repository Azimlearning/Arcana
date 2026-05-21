#!/usr/bin/env python3
"""
Arcana — secret-literal guard (PreToolUse on Write/Edit/MultiEdit).

Reads the Claude Code hook JSON on stdin. For file-write tools, scans the
content being written for known secret-literal patterns. If any pattern
matches, exits 2 with a clear reason on stderr (which Claude Code shows
to the model so it self-corrects).

Authority: NFR-SEC-03, .claude/rules/no-secret-literals.md
"""

from __future__ import annotations

import json
import re
import sys

PATTERNS: list[tuple[str, str]] = [
    ("Anthropic API key (sk-ant-…)",            r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    ("OpenAI API key (sk-…)",                   r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}"),
    ("Google service-account JSON",             r'"type"\s*:\s*"service_account"'),
    ("PEM private key block",                   r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("Pinecone-style key near identifier",      r"(?:PINECONE[A-Z_]*|pinecone[a-z_]*).{0,40}[A-Za-z0-9]{20,}"),
    ("High-entropy literal near 'key/secret/token/password'",
                                                r"(?:api[_-]?key|secret|token|password)[^A-Za-z0-9\n]{1,8}[A-Za-z0-9+/=_\-]{32,}"),
    ("AWS access key id",                       r"AKIA[0-9A-Z]{16}"),
    ("GitHub PAT",                              r"gh[pousr]_[A-Za-z0-9]{30,}"),
]

ALLOW_MARK = "pragma: allowlist secret"


def extract_content(data: dict) -> tuple[str, str] | None:
    """Return (file_path_hint, content_being_written) or None if not a write tool."""
    tool = data.get("tool_name", "")
    ti = data.get("tool_input", {}) or {}
    if tool == "Write":
        return ti.get("file_path", "?"), ti.get("content", "") or ""
    if tool == "Edit":
        return ti.get("file_path", "?"), ti.get("new_string", "") or ""
    if tool == "MultiEdit":
        edits = ti.get("edits", []) or []
        joined = "\n".join((e.get("new_string", "") or "") for e in edits)
        return ti.get("file_path", "?"), joined
    return None


def main() -> int:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        # Don't block on malformed hook input — but warn so it's visible.
        print(f"[check_secrets] warning: malformed hook JSON ({e}); pass-through.", file=sys.stderr)
        return 0

    pair = extract_content(data)
    if pair is None:
        return 0
    path_hint, content = pair

    # Strip lines explicitly allowlisted so they don't get scanned.
    lines = [ln for ln in content.splitlines() if ALLOW_MARK not in ln]
    scan = "\n".join(lines)

    findings: list[tuple[str, list[tuple[int, str]]]] = []
    for label, pattern in PATTERNS:
        hits: list[tuple[int, str]] = []
        for i, line in enumerate(lines, start=1):
            if re.search(pattern, line):
                hits.append((i, line.strip()[:160]))
                if len(hits) >= 3:
                    break
        if hits:
            findings.append((label, hits))

    if not findings:
        return 0

    msg = [f"🚫 Secret literal detected in {path_hint}", ""]
    for label, hits in findings:
        msg.append(f"  {label}:")
        for i, snippet in hits:
            msg.append(f"    line {i}: {snippet}")
        msg.append("")
    msg += [
        "Fix:",
        "  1. Move the value to .env (gitignored).",
        "  2. Add a field to api/core/settings.py (Settings class).",
        "  3. Read via settings.<field> — never os.environ in feature code.",
        "  4. Document the variable in .env.example and env_generation_guide.md §2.",
        "",
        "Genuine false positive? Append '# pragma: allowlist secret' to the line — sparingly.",
    ]
    print("\n".join(msg), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
