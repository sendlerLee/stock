# Loop Spec

## Goal

Advance request `stock-agent-full` for `stock`: Build full stock selection agent

## State Sources

- `AGENT_PROGRESS.md`
- `AGENT_FEATURES.json`
- `AGENT_HANDOFF.md`
- `QA_REPORT.md` when present
- Latest command outputs, test failures, logs, screenshots, or generated artifacts captured in the prior round

## Context Builder

At the start of each round, load only the state needed for the next decision:

1. Current request objective and feature status.
2. Last failure or feedback input.
3. Relevant source files, tests, logs, or QA evidence.
4. Active guardrails from project-level protocol files.

## Allowed Actions

- Make one small, request-scoped implementation or investigation increment.
- Run fast local checks needed for the done check.
- Update request-local progress, feature, handoff, QA, and loop state files.

## Capture Fields

Record after each round:

- Diff summary
- Commands run
- stdout/stderr or log summary
- Test, lint, typecheck, browser, QA, API, or data evidence
- Failure reason if not done
- Feedback for the next round
- New risks or required human decisions

## Done Check

Replace this placeholder with concrete completion criteria before running unattended or repeated rounds.

Examples:

- Focused tests pass and relevant acceptance criteria have evidence.
- QA report has no blocking issues.
- The failing case is reproduced, fixed, and covered by regression evidence.

## Feedback Path

If the done check fails, summarize the failure and next hypothesis in `LOOP_STATE.json.feedback_for_next_round` and `AGENT_HANDOFF.md`. The next round must start from that feedback instead of restarting from scratch.

## Stop Conditions

Stop before another round when any condition is true:

- `current_round` reaches `max_rounds`.
- Two consecutive rounds fail for the same reason.
- No clear progress for two rounds.
- Required environment, credentials, data, or tests are unavailable.
- The next action needs destructive commands, production writes, auto-merge, scheduling, expensive repeated execution, or cross-repo scope expansion.
- The done check is ambiguous or needs product/architecture judgment.

## Human Escalation

Ask for direction when stop conditions are met or when continuing could cause cost, data, production, or scope risk.
