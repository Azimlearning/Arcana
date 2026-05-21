# Arcana — developer shortcuts.
# Targets stay thin; real work lives in package scripts and pyproject tasks.

.PHONY: help install codegen codegen-check build typecheck lint test \
        ingest-demo bench up up-api up-web clean

help:
	@echo "Arcana - make targets"
	@echo "  install         pnpm install + uv sync (run once)"
	@echo "  codegen         regenerate api/genui/_generated.py from packages/schema"
	@echo "  codegen-check   fail if api/genui/_generated.py is out of sync"
	@echo "  build           build schema + web (production)"
	@echo "  typecheck       typecheck schema + web + api/"
	@echo "  lint            ruff check api/ + eslint web/"
	@echo "  test            pytest + vitest"
	@echo "  ingest-demo     ingest PDFs under eval/corpus/"
	@echo "  bench           hybrid vs flat baseline (P1 stub)"
	@echo "  up              print two-terminal dev instructions"
	@echo "  up-api          uvicorn on :8000 (one terminal)"
	@echo "  up-web          next dev on :3000 (other terminal)"
	@echo "  clean           remove build artefacts"

install:
	corepack pnpm install
	uv sync --dev

codegen:
	corepack pnpm --filter @arcana/schema codegen

codegen-check:
	corepack pnpm --filter @arcana/schema codegen:check

build:
	corepack pnpm --filter @arcana/schema build
	corepack pnpm --filter @arcana/web build

typecheck:
	corepack pnpm --filter @arcana/schema typecheck
	corepack pnpm --filter @arcana/web typecheck
	uv run --with pyright pyright api/

lint:
	uv run ruff check api/
	corepack pnpm --filter @arcana/web lint

test:
	uv run pytest -q api/
	corepack pnpm --filter @arcana/web test

ingest-demo:
	uv run python -m eval.ingest_demo

bench:
	uv run python -m eval.run_benchmark

up:
	@echo "Run these in TWO terminals:"
	@echo "  Terminal A:  make up-api"
	@echo "  Terminal B:  make up-web"

up-api:
	uv run uvicorn api.main:app --reload --port 8000

up-web:
	corepack pnpm --filter @arcana/web dev

clean:
	# Cross-platform clean - runs through Python so it works in cmd.exe,
	# PowerShell, Git Bash, and POSIX shells alike. GNU Make is still
	# required (Windows users need Git Bash / WSL / MSYS).
	uv run python -c "import pathlib, shutil; \
[shutil.rmtree(p, ignore_errors=True) for root in ['packages', 'web', '.'] \
 for p in pathlib.Path(root).rglob('dist')] \
+ [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')] \
+ [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('.next') if 'node_modules' not in str(p)] \
+ [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('.pytest_cache')]"
