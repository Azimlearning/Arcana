---
applies_to: "packages/schema/**"
---

# Rule: Schema-first wire contract

**Authority:** PRD §13.1, §16, §19; project_file_structure.md golden rule #1; R-10 (schema drift).

## The contract

`packages/schema/` is the **single source of truth** for every type that crosses the wire. Anything sent between backend and frontend — `UIBlock`, `ChatRequest`, `AgentResult`, every payload (`CitedSummaryData`, `FlashcardDeck`, etc.), every entity — is defined here once.

## What this means in practice

- **Define types here first, code second.** A new payload starts in `packages/schema/payloads.ts`. Then `codegen/to_python.ts` is rerun, producing Pydantic models in `api/`. Then the agent emits it. Then the component renders it. In that order.
- **Never duplicate a type.** If a Python file declares a class with the same shape as something in `packages/schema/`, that is a violation. Import the codegen'd model instead.
- **TypeScript is authoritative.** When TS and Python diverge, TS wins — Python regenerates.
- **One block = one variant.** Every `UIBlock` variant has exactly one `kind` value, one schema, one renderer, one row in `registry.ts`.

## Before changing anything in here

Stop. Anything you change here ripples to: codegen, every agent that emits the type, the validator (`api/genui/validate.py`), the streamer, the SSE consumer (`web/lib/stream.ts`), the registry, the renderer. If the schema isn't right, none of the rest can be.

Run the `schema-first-change` skill — it walks the exact step order.

## Checklist

- [ ] Type added/edited in the correct file (`entities.ts`, `blocks.ts`, `payloads.ts`, or `api.ts`).
- [ ] `codegen/to_python.ts` re-run; emitted Pydantic models committed.
- [ ] No duplicate definitions in `api/` — search for the class name.
- [ ] If it's a `UIBlock` variant: new `kind` literal, one row in `web/components/genui/registry.ts`, one renderer file under `web/components/genui/`, all four states implemented.
- [ ] Server-side validator (`api/genui/validate.py`) updated to accept the new variant.
- [ ] Commit message references the FR/NFR ID (e.g. `feat(schema): SocraticDialog payload — supports FR-LRN-08`).
