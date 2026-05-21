# Arcana — Decisions Log

> Lightweight ADR-style record of choices made during the build. The point isn't documentation theatre — it's that Claude Code sessions don't carry memory between runs, and the spec has open questions (Q-03 to Q-10) that may get resolved by *assumption* mid-build. Capturing those assumptions here keeps future sessions, the supervisor review, and the FYP defence on the same page.
>
> **When to write here:**
> - You hit an open question (Q-03..Q-10) without an answer and pick a path to keep moving.
> - You make a choice not explicitly in the PRD (a library, an algorithm constant, a UX detail).
> - You discover a spec contradiction and resolve it.
> - You opt out of a rule with a stated reason (e.g. `# pragma: allowlist secret`).
>
> **Format:** one short entry per decision. Date, the question, the decision, why, and what would force a revisit.

---

## Template

```markdown
### YYYY-MM-DD — <short title>

- **Status:** ASSUMED | DECIDED | REVISITED
- **Context:** what was unclear or open. Reference FR/NFR/R/Q IDs.
- **Decision:** what we're doing.
- **Why:** the trade-off that tipped it.
- **Revisit if:** the condition that would force reconsidering.
```

---

## Entries

<!-- New entries go below this line, newest first. -->

### 2026-05-21 — `.claude/` operating layer scaffolded

- **Status:** DECIDED
- **Context:** No mechanism enforced the eight invariants and the architectural rules — they lived only in spec prose.
- **Decision:** Created `.claude/` with a trimmed `CLAUDE.md`, path-scoped rule files, three subagents (schema-guardian, code-reviewer, qa-runner), four Skills, and three hooks (secret-literal block, dependency-direction block, post-write format + check).
- **Why:** Spec invariants enforced in review only are spec invariants honoured maybe. Hooks turn them into mechanism.
- **Revisit if:** Claude Code hook/agent schema changes (track release notes); new invariants emerge from PRD updates.
