---
applies_to: "**/*.py, **/*.ts, **/*.tsx, **/*.js, **/*.jsx"
---

# Rule: No secret literals in source

**Authority:** PRD §11A.3 (invariant #8); NFR-SEC-03; `docs/env_generation_guide.md` §5.

## The rule

Secrets (API keys, tokens, passwords, service-account keys, signed URLs) **never** appear as string literals in source. Ever.

- Backend: read everything through `api/core/settings.py` (`Settings(BaseSettings)`). Never `os.environ["..."]` in feature code.
- Frontend: only `NEXT_PUBLIC_*` vars are exposed to the browser, and only **publishable** identifiers (Firebase client config) — never service-account or server-side keys.
- Tests, fixtures, examples: use placeholders (`"sk-test-EXAMPLE"`, `"REDACTED"`) — they must be obviously fake.

## What gets blocked

The pre-commit hook (`.claude/hooks/check_secrets.sh`) greps every changed file for these patterns and blocks the commit if any match:

- Anthropic: `sk-ant-`
- OpenAI: `sk-` followed by 20+ alphanumeric
- Pinecone: long alphanumeric near `PINECONE`
- Google service-account: `"type": "service_account"`
- Firebase private key: `BEGIN PRIVATE KEY`
- Generic 32+ char hex/base64 near words like `api_key`, `secret`, `token`, `password`

A matched literal is logged to stderr with the file and line, exit code 2.

## False positives

If the match is genuinely safe (a docstring example, a test placeholder labelled clearly), put `# pragma: allowlist secret` on the line. Use this sparingly — every allowlist annotation should be reviewable on its own.

## What to do instead

- **New secret:** add a variable name + comment to `.env.example`; add the field to `Settings`; document where to obtain it in `docs/env_generation_guide.md` §2.
- **Local development:** keep the real value in `.env` (gitignored). Verify `git status` doesn't list it.
- **CI / deploy:** secrets live in the platform's secret store (GitHub Actions secrets, etc.).

## Checklist

- [ ] No literal that matches a known key pattern.
- [ ] `.env.example` lists the new variable with an empty value and a one-line comment.
- [ ] `Settings` class has the new field with a sensible default (or `None` if optional).
- [ ] `env_generation_guide.md` §2 has acquisition steps.
- [ ] The real value is in `.env` locally and the platform secret store remotely — never both, never in git.
