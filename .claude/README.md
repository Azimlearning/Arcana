# `.claude/` — Arcana operating layer

> What lives in here and how it loads. The five spec docs in `docs/` are the source of truth; this folder is the **mechanism** that makes Claude Code respect them.

## Layout

```
.claude/
├── settings.json              # permissions + hooks wiring (loaded on session start)
├── README.md                  # this file
├── rules/                     # path-scoped behavior rules (load via applies_to glob)
│   ├── schema-first.md
│   ├── dependency-direction.md
│   ├── agent-composability.md
│   ├── genui-component.md
│   └── no-secret-literals.md
├── agents/                    # subagents (run in isolated context, invoke explicitly)
│   ├── schema-guardian.md
│   ├── code-reviewer.md
│   └── qa-runner.md
├── skills/                    # repeatable recipes (load on demand by description)
│   ├── genui-component/SKILL.md
│   ├── new-agent/SKILL.md
│   ├── new-retriever/SKILL.md
│   └── schema-first-change/SKILL.md
├── hooks/                     # deterministic guards (run automatically)
│   ├── check_secrets.py       # PreToolUse Write|Edit|MultiEdit
│   ├── check_imports.py       # PreToolUse Write|Edit|MultiEdit (Python only)
│   └── format_and_check.py    # PostToolUse Write|Edit|MultiEdit
└── memory/
    ├── decisions.md           # ADR-lite log — record assumptions as they're made
    └── preflight.md           # one-page gate before Claude Code starts the build
```

## What loads when

| Layer | Always loaded | Loads on path match | Loads on demand | Runs deterministically |
|---|---|---|---|---|
| `CLAUDE.md` (root) | ✓ | | | |
| `rules/*.md` | | ✓ (path-scoped) | | |
| `agents/*.md` | | | ✓ (explicit invocation) | |
| `skills/*/SKILL.md` | | | ✓ (description match) | |
| `hooks/*` | | | | ✓ (tool lifecycle) |

The point of the layout: **the root brief stays short**, project-specific behavior loads only where it's relevant, repeatable recipes load only when needed, and the truly non-negotiable rules (secret-literals, dependency-direction) are enforced by hooks regardless of what the model decides.

## How to add to this layer

- **New rule** — short, path-scoped via `applies_to:` frontmatter; cite the PRD section and FR/NFR ID. Don't add to `CLAUDE.md` (keep it lean).
- **New subagent** — `agents/<name>.md` with frontmatter `name`, `description`, `tools`, `model`. Read-only by default unless it genuinely needs to write.
- **New skill** — `skills/<name>/SKILL.md` with frontmatter `name` + `description`. The description is what tells Claude when to load it — be specific about triggers.
- **New hook** — script under `hooks/`, wired in `settings.json`. Prefer exit-2-with-stderr over silent failure; the model needs to see what went wrong.

## Verifying it works

Run through `memory/preflight.md`. The subagent smoke tests and the hook smoke tests at the bottom of that file confirm the layer is wired correctly before the first real build session.

## Authority

Every rule, skill, and hook here cites a section in the spec docs and a FR/NFR/R ID. When this layer disagrees with the spec, the spec wins — surface the conflict and update this layer.
