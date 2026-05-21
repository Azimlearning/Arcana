---
applies_to: "web/components/genui/**"
---

# Rule: GenUI components are registry-driven and fully stateful

**Authority:** PRD §13–§14, §11A.3 (invariants #2, #3); `docs/uiux_plan.md` (the design authority — read §§1–6 before styling); FR-UI-03, FR-UI-04, FR-UI-09, NFR-MNT-02, NFR-USE-02.

## The component contract

A GenUI component is the **only** thing the user sees. Every component:

1. Has exactly one entry in `web/components/genui/registry.ts` keyed by its `UIBlock.kind`.
2. Renders **only** from a typed payload defined in `packages/schema/payloads.ts`. No props from agents directly.
3. Implements **all four states** via `BlockStates.tsx`: Empty, Loading (skeleton), Partial (streaming), Error (with retry where applicable). Missing any one is incomplete (NFR-USE-02, FR-UI-09).
4. Uses **design tokens only** from `uiux_plan.md` §2. No raw hex colors, no inline font families, no magic spacing values.
5. Is selected by the **UI Agent only**. No other code path adds a block to the stream.

## What this means in practice

- Never write `<div style={{ color: '#6B5B47' }}>` — use `var(--accent)` or the Tailwind class wired to the token.
- Never let an agent ship raw HTML or markdown to the frontend. The schema is the wire; the renderer is the boundary.
- Never bypass the registry. `renderBlock(block)` is the single dispatch point — no direct component imports from outside the registry.

## The three-step recipe (use the `genui-component` skill)

To add a new component:

1. **Schema:** add a variant to `UIBlock` in `packages/schema/blocks.ts` and a payload type in `packages/schema/payloads.ts`. Re-run `to_python.ts` codegen.
2. **Renderer:** create `web/components/genui/<Name>.tsx` with Empty/Loading/Partial/Error states. Style with tokens from `uiux_plan.md`.
3. **Register:** add one row to `web/components/genui/registry.ts` mapping the new `kind` to the renderer.

That's it. If you touch anything else (the streamer, the validator, the UI Agent's catalog), you've gone off-pattern — re-read the skill.

## The mockup is a reference, not a spec

`arcana_mockup_v3.html` demonstrates 11 of the 24 components (see `uiux_plan.md` §10). When wiring real components, use the mockup for layout/style intent and `uiux_plan.md` for the authoritative tokens, states, and panel rules. When they disagree, `uiux_plan.md` wins.

## Checklist

- [ ] One new `kind` literal in `packages/schema/blocks.ts`; one payload in `packages/schema/payloads.ts`.
- [ ] One renderer file `<Name>.tsx`.
- [ ] One row in `registry.ts`.
- [ ] Empty / Loading / Partial / Error states implemented (BlockStates.tsx).
- [ ] No raw hex, no inline fonts, no hard-coded spacing — tokens only.
- [ ] Validator (`api/genui/validate.py`) accepts the new variant.
- [ ] Component appears in `uiux_plan.md` §4 catalog (update it if this is a new addition vs. an existing catalog entry).
