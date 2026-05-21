---
name: schema-first-change
description: Use whenever a change touches the wire between backend and frontend — adding/modifying any UIBlock variant, payload, entity, or API request/response in packages/schema/. Walks the exact order (TS first → codegen → Python → validator → emitter → renderer → registry) so the contract stays intact and nothing in api/ ends up duplicating types.
---

# Skill: Make a schema-first change (anything that crosses the wire)

**Authority:** PRD §13.1, §16, §19; `.claude/rules/schema-first.md`; R-10 (schema drift).

`packages/schema/` is the single source of truth. Every change that crosses the wire starts here, in TypeScript, and propagates outward in a fixed order. Skip a step and you create schema drift that takes hours to debug.

## The order (never improvise)

```
1. TS definition in packages/schema/
2. Codegen → Python models in api/
3. Server-side validator update
4. Agent payload emitter
5. Renderer (web/components/genui/)
6. Registry row
7. Doc update (uiux_plan.md if it's a UIBlock)
```

Each step depends on the one before. Don't open the next file until the current step is committed (or at least staged and stable).

## Step 1 — TypeScript first

Pick the right file in `packages/schema/`:

- `entities.ts` — domain objects (Document, Chunk, GraphNode, Notebook, UserProfile, etc.)
- `blocks.ts` — the `UIBlock` discriminated union
- `payloads.ts` — block payload types (`CitedSummaryData`, `FlashcardDeck`, etc.)
- `api.ts` — request/response shapes (`ChatRequest`, `IngestRequest`, `AgentResult`)

Add or modify the type. Constraints:

- Concrete, narrow types. No `any`. Optional fields explicit (`field?: T` or `T | null`).
- New `UIBlock.kind` literals are kebab-case and globally unique.
- Discriminated unions over the kind: `{ kind: "x"; data: XData; meta: BlockMeta }`.
- Field names match the agent's naming for the same concept (don't rename across the wire).

## Step 2 — Codegen

```bash
pnpm --filter @arcana/schema codegen
```

Verify:

- Pydantic models are emitted into `api/` at the configured path.
- No manual edits in the emitted files. They're regenerated; edits are lost.
- `git diff` should show TS additions + matching Python additions, nothing else.

If codegen fails, fix the TS — the emitted output reflects the TS exactly.

## Step 3 — Server-side validator

Open `api/genui/validate.py` (for `UIBlock` changes) or the relevant request validator (for API shapes).

- Add the new variant / field to the validation set.
- **Fail closed.** Anything that doesn't match the schema must be rejected before it streams to the frontend (NFR-SEC-04, FR-UI-03).
- A new optional field still needs a validator update if it has constraints (range, enum, regex).

## Step 4 — Backend emitter

Update whichever agent or service emits the new shape. Constraints:

- Construct the payload using the codegen'd Pydantic model — never a raw dict that happens to match.
- No manual JSON shaping; let the serializer handle it.
- If this is a new `UIBlock`, only the UI Agent emits it (invariant #3). Other agents return payload data and let the UI Agent wrap.

## Step 5 — Frontend consumer / renderer

Open the consumer:

- For `UIBlock` changes — the renderer at `web/components/genui/<Name>.tsx`. See the `genui-component` skill for the four-state requirement.
- For API request/response changes — the relevant call site under `web/lib/` and the page/component that uses it.
- Types come from `packages/schema/` directly. No re-declaring.

## Step 6 — Registry

For `UIBlock` changes only: one row in `web/components/genui/registry.ts` mapping the new `kind` to the renderer. `renderBlock(block)` dispatches; nothing else imports the renderer directly.

## Step 7 — Update the design doc

For new components: add a row to `docs/uiux_plan.md` §4 catalog. Keeping the doc accurate is part of done — otherwise the master index drifts and future changes start from the wrong picture.

## Validation pass

Before committing:

1. `pnpm --filter @arcana/schema codegen --check` — exit 0 means TS and Python are in sync.
2. Grep for any class in `api/` that duplicates a `packages/schema/` definition. There should be none.
3. Grep for raw dict construction matching the new payload shape — it should be the Pydantic model instead.
4. Confirm the new variant flows: emitter → validator → SSE → consumer → renderer → screen.

## Done checklist (paste into the commit)

- [ ] TS first in the right `packages/schema/` file.
- [ ] Codegen run; Python models in sync; nothing duplicated in `api/`.
- [ ] Validator updated; fails closed.
- [ ] Emitter constructs via the Pydantic model.
- [ ] Consumer/renderer types come from `packages/schema/`.
- [ ] Registry row added (if `UIBlock`).
- [ ] `docs/uiux_plan.md` updated (if it's a new component).
- [ ] Commit references the FR-UI-* / FR-* / R-10 ID.
- [ ] `schema-guardian`, `code-reviewer`, and `qa-runner` subagents report green.
