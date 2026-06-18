# Agent Harness Protocol

This is the canonical project protocol for autonomous coding agents working on `stock`. Codex, Claude Code, Cursor, and similar agents should follow this file.

## Core Rules

- Use the smallest harness that can safely handle the task.
- Classify project state before request state: new_empty, existing_unharnessed, existing_harnessed, or legacy_complex.
- Keep project-level memory at the repo root.
- Keep request-level memory under `agent-runs/<request-id>/`.
- Classify each user request automatically as continue, new, or supersede.
- Classify task autonomy as Class A, B, or C before choosing how much the agent may decide.
- Make one small, verifiable increment per run.
- Use code review gates before verification when task class, loop, reference use, or change risk requires it.
- Keep a compact context pack for B/C, loop-enabled, review-gated, or cross-session work.
- Do not mark work passed without evidence.
- Preserve user changes and never revert unrelated work.

## Project State

- New/empty project: full bootstrap is safe.
- Existing, unharnessed project: add a thin harness and preserve local conventions.
- Existing, harnessed project: reuse project-level files; create request-scoped files for new work.
- Legacy/complex project: write `PROJECT_STATE.md`, tighten scope, and require safety gates before implementation.

## Request Classification

- Continue the active request when the new message refines the same objective, target object, acceptance frame, repo/module boundary, or reported defect.
- Create a new request when the objective, target object, acceptance frame, repo/module boundary, or validation workflow is materially different.
- Supersede an old request when the user asks to redo the same broad goal with a different direction or abandon the previous approach.
- Ask the user only if ambiguity could cause destructive edits, cross-repo scope mistakes, or irreversible workflow churn.

## Start Of Run

1. Read `AGENT_REQUESTS.json` if it exists.
2. Read the active request directory under `agent-runs/<request-id>/` if present.
3. Read `PROJECT_STATE.md`, project-level `AGENT_PROGRESS.md`, `AGENT_FEATURES.json`, and `AGENT_HANDOFF.md` if present.
4. Read request-local `CONTEXT_PACK.md`, `CODE_REVIEW.md`, `LOOP_STATE.json`, and `STAGE_PLAN.md` when present.
5. Inspect `init.sh` before running it.
6. Choose one pending feature/task and state the review gate, done check, stop condition, and intended verification.

## Execution

- Prefer fast local feedback first: lint, typecheck, focused unit tests, small e2e, browser console, logs.
- Update request-local files before project-level files for request-scoped work.
- Update top-level files only for durable project state, cross-request rules, or global blockers.
- Preserve existing project conventions and do not overwrite project-level instructions without an explicit harness-update request.
- Use `CODE_REVIEW.md` before verification when review gate is active.
- Keep `CONTEXT_PACK.md` current when continuity risk exists.
- Keep guardrails machine-checkable where possible: tests, linters, scope files, CI limits, structural checks.

## Evaluation

- For app/product/frontend work, maintain `PRODUCT_SPEC.md` and `QA_REPORT.md` in the request directory.
- Treat generator self-assessment as insufficient.
- Completion requires external evidence: test output, e2e result, browser screenshot, logs, API/DB check, or equivalent.

## End Of Run

1. Update request-local `AGENT_PROGRESS.md`.
2. Update request-local `AGENT_FEATURES.json` statuses only for verified items.
3. Update request-local `CODE_REVIEW.md` and `CONTEXT_PACK.md` when present.
4. Update request-local `AGENT_HANDOFF.md`.
5. Update request-local `LOOP_STATE.json` and `AGENT_REQUESTS.json` status if needed.
6. Report review result, verification evidence, and residual risk.
