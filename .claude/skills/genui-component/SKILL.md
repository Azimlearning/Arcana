---
name: genui-component
description: Use when adding a new generative-UI component to Arcana — when the user asks to support a new typed output (e.g. "add a citation-network block", "build the contradiction-card component"), or when a new UIBlock variant needs to ship end-to-end. Walks the schema → renderer → registry recipe with the four required states and design-token discipline.
---

# Skill: Add a new GenUI component (end-to-end)

**Authority:** PRD §13–§14; `docs/uiux_plan.md` §§4 (catalog), §5 (state taxonomy), §2 (tokens); `.claude/rules/genui-component.md`, `.claude/rules/schema-first.md`.

A GenUI component crosses three layers — schema, renderer, registry — and must implement four states. Skip any step and the wire contract or the UX breaks. Follow this order exactly.

## Step 1 — Schema (TypeScript first, always)

Open `packages/schema/`.

1. In `payloads.ts`, define the payload type. Use existing primitive types where possible; no `any`, no untyped fields.
2. In `blocks.ts`, add the variant to the `UIBlock` union:
   ```ts
   | { kind: "<new-kind>"; data: <NewPayload>; meta: BlockMeta }
   ```
   The `kind` literal must be unique and kebab-case.
3. Run the codegen:
   ```bash
   pnpm --filter @arcana/schema codegen
   ```
   Verify the emitted Pydantic model appears in `api/` (or wherever `to_python.ts` outputs).

**Commit checkpoint:** `feat(schema): <new-kind> block + payload — supports FR-UI-<id>`.

## Step 2 — Server-side validator

Open `api/genui/validate.py`. Add the new variant to the validation set so blocks of this `kind` pass through; anything malformed must fail closed before streaming. This satisfies NFR-SEC-04.

## Step 3 — UI Agent catalog awareness

Open `api/agents/tier3/ui_agent.py`. Add the new component to the catalog the UI Agent draws from, with: when to pick it (intent / mode signal), what payload it expects, and any precedence rules versus existing components. Only the UI Agent picks components — never let another agent select it directly (invariant #3).

## Step 4 — Renderer

Create `web/components/genui/<Name>.tsx`. Requirements:

- Props are the codegen'd payload type — no manual re-typing.
- All styling uses design tokens from `docs/uiux_plan.md` §2. No raw hex, no inline font families, no magic spacing. Tailwind utility classes wired to the tokens, or `var(--token)` in CSS.
- Implement all **four states** via `BlockStates.tsx`:
  - **Empty** — the agent ran but produced nothing of substance (e.g. no citations found). Show a calm, instructive placeholder.
  - **Loading** — pre-stream skeleton. Match the eventual layout so the component doesn't reflow when data arrives.
  - **Partial** — streaming. Progressive disclosure: render what's available, leave skeletons for what isn't.
  - **Error** — failure inside this block. Show the cause if safe, offer a retry where applicable.
- No browser storage (localStorage, sessionStorage) — React state or zustand only.
- No direct API calls — components are pure renderers; data arrives via props.

## Step 5 — Register

Open `web/components/genui/registry.ts`. Add **one row** mapping the new `kind` to the renderer:

```ts
import { NewBlock } from "./<Name>";
// …
"<new-kind>": NewBlock,
```

`renderBlock(block)` will dispatch to it. No other call sites import the renderer directly.

## Step 6 — Update the design doc

Open `docs/uiux_plan.md` §4. Add the new component to the catalog table with: panel (Sources / Chat / Studio), phase (P0 / P1 / P2), the modes it appears in, the payload type, and a one-line description. Keeping the doc current is part of "done" — otherwise the master index drifts.

## Step 7 — Smoke test

Either run a unit test on the renderer (Vitest) or trigger an end-to-end flow that exercises the new block. Minimum bar: the component renders in all four states without throwing.

## Done checklist (paste into the commit)

- [ ] New `kind` in `packages/schema/blocks.ts`; payload in `packages/schema/payloads.ts`.
- [ ] Codegen run; Python model in sync.
- [ ] Validator (`api/genui/validate.py`) accepts the new variant.
- [ ] UI Agent catalog updated with selection criteria.
- [ ] `<Name>.tsx` renderer with all four states, tokens-only styling.
- [ ] One row in `registry.ts`.
- [ ] `docs/uiux_plan.md` §4 updated.
- [ ] Smoke test green.
- [ ] Commit references the FR-UI-* ID.
- [ ] `code-reviewer` and `qa-runner` subagents report green.
