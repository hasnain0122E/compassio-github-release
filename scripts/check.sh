#!/usr/bin/env bash
# Runs every Phase 0 quality gate. Usage (from anywhere):
#   bash scripts/check.sh            # Python + web
#   bash scripts/check.sh --skip-web # Python only
set -euo pipefail

cd "$(dirname "$0")/.."

step() {
  echo "==> $1"
  shift
  "$@"
}

step "uv sync --locked" uv sync --locked
step "ruff check" uv run ruff check .
step "ruff format --check" uv run ruff format --check .
step "mypy" uv run mypy
step "pytest" uv run pytest

if [[ "${1:-}" != "--skip-web" ]]; then
  cd apps/web
  step "pnpm install --frozen-lockfile" pnpm install --frozen-lockfile
  step "pnpm lint" pnpm lint
  step "pnpm typecheck" pnpm typecheck
  step "pnpm build" pnpm build
fi

echo "All checks passed."
