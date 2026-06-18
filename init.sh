#!/usr/bin/env bash
set -euo pipefail

echo "[agent-harness] cwd: $(pwd)"

if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[agent-harness] git branch: $(git branch --show-current 2>/dev/null || true)"
  echo "[agent-harness] recent commits:"
  git log --oneline -5 || true
fi

echo "[agent-harness] TODO: add fast project-specific checks here."
echo "[agent-harness] Examples: npm test -- --runInBand, npm run typecheck, pytest -q, cargo test"
