# Context Pack

## Request

- Project: `stock`
- Request ID: `stock-agent-full`
- Title: Build full stock selection agent

## Current Objective

- 

## Active Stage Or Increment

- 

## Must-Read Files

- `AGENT_PROGRESS.md`: current status and evidence
- `AGENT_FEATURES.json`: task board and acceptance criteria
- `AGENT_HANDOFF.md`: continuation notes

## Recent Decisions And Rationale

- 

## Rejected Approaches

- 

## Important Constraints And Non-Goals

- 

## Known Pitfalls

- 

## Changed Files Summary

- 

## Verification And Review History

- 

## Current Blockers Or Open Questions

- 

## Next Prompt Seed

Resume this request by reading `CONTEXT_PACK.md`, `AGENT_PROGRESS.md`, `AGENT_FEATURES.json`, `AGENT_HANDOFF.md`, `LOOP_STATE.json` if present, `CODE_REVIEW.md` if present, and `STAGE_PLAN.md` if present. Continue from the active stage/increment above. Do not repeat rejected approaches. Verify with the checks listed in the request-local feature file.

## Run Update - 2026-06-18T06:32:54Z

- Current update: Built full stock selection agent with snapshot provider, scanner, CLI, API endpoint, reports, tests, and real sample validation.
- Result: passed
- Next prompt seed: Resume `stock-agent-full` from this update. Read `CONTEXT_PACK.md`, `AGENT_PROGRESS.md`, `AGENT_FEATURES.json`, `AGENT_HANDOFF.md`, `CODE_REVIEW.md` if present, and `LOOP_STATE.json` if present. Next action: Use scripts/run_stock_agent.py or POST /agent/scan with explicit symbols; future work can add full-market universe discovery and scheduled reports..

### Must Carry Forward
- None.

## Run Update - 2026-06-18T06:41:55Z

- Current update: Added as-of daily report generation and produced 2026-06-17 sample report from discovered A-share universe.
- Result: sample report generated
- Next prompt seed: Resume `stock-agent-full` from this update. Read `CONTEXT_PACK.md`, `AGENT_PROGRESS.md`, `AGENT_FEATURES.json`, `AGENT_HANDOFF.md`, `CODE_REVIEW.md` if present, and `LOOP_STATE.json` if present. Next action: Review reports/stock_agent_report_2026-06-17.md/json; next increment can add scheduled post-close automation and larger universe batching..

### Must Carry Forward
- None.

## Run Update - 2026-06-18T08:53:21Z

- Current update: Enhanced stock-agent reports with per-stock status labels and scoring dimensions, then generated a 2026-06-18 A/HK/US selection result report.
- Result: passed this increment
- Next prompt seed: Resume `stock-agent-full` from this update. Read `CONTEXT_PACK.md`, `AGENT_PROGRESS.md`, `AGENT_FEATURES.json`, `AGENT_HANDOFF.md`, `CODE_REVIEW.md` if present, and `LOOP_STATE.json` if present. Next action: Review report thresholds with user feedback; next safe increment is to tune scoring cutoffs so high-quality setups can graduate from waiting_confirm to buy_candidate under explicit risk rules..

### Must Carry Forward
- Report status labels map verdicts to user-facing actions: buy/staged entry, wait, hold-watch, reduce/protect, avoid.
- The 2026-06-18 run intentionally reported zero direct buy_candidate items because current scores did not clear confirmation gates.
- Some A-share Eastmoney fund-flow calls returned RemoteDisconnected, so flow dimension can mean missing confirmation rather than verified outflow.

## Run Update - 2026-06-18T09:27:18Z

- Current update: Added granular action states, treated missing fund-flow as unconfirmed instead of negative, and stopped after real A/HK/US scan produced actionable stocks.
- Result: actionable stocks found
- Next prompt seed: Resume `stock-agent-full` from this update. Read `CONTEXT_PACK.md`, `AGENT_PROGRESS.md`, `AGENT_FEATURES.json`, `AGENT_HANDOFF.md`, `CODE_REVIEW.md` if present, and `LOOP_STATE.json` if present. Next action: Review reports/actionable_stocks_2026-06-18.md; next optional increment is fund-flow reliability and per-market threshold calibration..

### Must Carry Forward
- Stopped after actionable stocks appeared per user instruction; did not expand to full-market discovery.
- Kept AgentVerdict buckets for compatibility and added ActionState for execution-level status.
- A-share Eastmoney fund-flow endpoint still intermittently disconnects; current output labels those cases as unconfirmed.

## Run Update - 2026-06-18T10:30:00Z

- Current update: 回测系统实现 7/9 任务完成（universe/engine/results/report + 6 单元测试）。
- Result: implementation in progress

### Must Carry Forward
- 回测直接复用 src.agent.stock_agent.StockAgent.evaluate，零逻辑漂移——这是核心约束，任何"优化"都不能脱离生产代码。
- run_backtest 有可选 kline_cache 参数：测试注入绕过 DB，生产不传走 prefetch_klines。
- 冷却规则：ENTRY_STATES = {BUY_NOW, PROBE}，建仓后 60 交易日内不重复，冷却期内信号忽略（不延迟、不排队）。
- 收益公式：entry=次日开盘，exit=entry+N 天收盘，return_n = exit_close/entry_open - 1，数据不足标 None。
- 已知偏差：PE/PB/ROE/分红/行业用最新值（未来函数），trading 模式权重合计 0.20，已在 report.py 硬编码标注。
- 测试必须离线：FakeProvider 注入 + kline_cache，不依赖网络或真实 DB。
- git 已初始化并推送到 github.com/sendlerLee/stock（main 分支）。
- 设计文档：docs/superpowers/specs/2026-06-18-backtest-design.md
- 实现计划：docs/superpowers/plans/2026-06-18-backtest.md

### Next Prompt Seed
Resume from Task 8：实现 scripts/run_backtest.py（CLI 入口，--start/--end/--mode/--symbols/--output-dir），复用 engine.run_backtest + results.build_trades/compute_metrics/compute_benchmark + report.render_report。然后 Task 9 真实数据 smoke。
