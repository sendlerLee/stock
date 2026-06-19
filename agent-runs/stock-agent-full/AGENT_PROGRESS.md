# Agent Progress

## Request

- Project: `stock`
- Request ID: `stock-agent-full`
- Title: Build full stock selection agent

## Current Objective

Define the current objective for this request.

## Current Increment

- Status: pending
- Selected feature/task:
- Intended verification:

## Completed

- None yet.

## Evidence

- None yet.

## Blockers And Risks

- None yet.

## Next Action

1. Fill request-local `AGENT_FEATURES.json` with concrete tasks.
2. Run project-level `init.sh` only after inspecting it.
3. Select one pending task and verify it with fast local feedback.

## History

- Initialized request-scoped harness files.

## Run Update - 2026-06-18T06:32:54Z

- Request: `stock-agent-full`
- Summary: Built full stock selection agent with snapshot provider, scanner, CLI, API endpoint, reports, tests, and real sample validation.
- Result: passed
- Next: Use scripts/run_stock_agent.py or POST /agent/scan with explicit symbols; future work can add full-market universe discovery and scheduled reports.

### Evidence
- 26 tests passed; real trading scan produced 华虹宏力 watch and 招商银行 avoid for short-term trading; real position scan produced 招商银行 watch and 688347 avoid.

### Commands
- /Users/didi/conda/bin/python -m pytest tests/test_stock_agent.py tests/test_agent_snapshot.py tests/test_agent_scanner.py tests/test_agent_api.py tests/test_signals.py tests/test_indicators.py -q
- /Users/didi/conda/bin/python scripts/run_stock_agent.py --symbols A:600036,A:688347,HK:01347 --mode trading
- /Users/didi/conda/bin/python scripts/run_stock_agent.py --symbols A:600036,A:688347,HK:01347 --mode position

### Changed Files Or Artifacts
- src/agent/providers.py
- src/agent/snapshot.py
- src/agent/scanner.py
- src/agent/stock_agent.py
- src/api/routers/agent.py
- src/api/main.py
- scripts/run_stock_agent.py
- tests/test_agent_snapshot.py
- tests/test_agent_scanner.py
- tests/test_agent_api.py
- README.md

### Decisions
- None.

### Blockers And Risks
- None.

## Run Update - 2026-06-18T06:41:55Z

- Request: `stock-agent-full`
- Summary: Added as-of daily report generation and produced 2026-06-17 sample report from discovered A-share universe.
- Result: sample report generated
- Next: Review reports/stock_agent_report_2026-06-17.md/json; next increment can add scheduled post-close automation and larger universe batching.

### Evidence
- Generated 20-stock discovered A-share report: 0 buy candidates, 12 watchlist, 8 risk/avoid, 0 errors.

### Commands
- /Users/didi/conda/bin/python scripts/daily_stock_report.py --as-of 2026-06-17 --limit 20 --mode trading --output-dir reports
- /Users/didi/conda/bin/python -m pytest tests/test_agent_snapshot.py tests/test_agent_scanner.py -q

### Changed Files Or Artifacts
- src/agent/providers.py
- src/agent/__init__.py
- scripts/daily_stock_report.py
- tests/test_agent_snapshot.py
- reports/stock_agent_report_2026-06-17.json
- reports/stock_agent_report_2026-06-17.md

### Decisions
- None.

### Blockers And Risks
- None.

## Run Update - 2026-06-18T08:53:21Z

- Request: `stock-agent-full`
- Summary: Enhanced stock-agent reports with per-stock status labels and scoring dimensions, then generated a 2026-06-18 A/HK/US selection result report.
- Result: passed this increment
- Next: Review report thresholds with user feedback; next safe increment is to tune scoring cutoffs so high-quality setups can graduate from waiting_confirm to buy_candidate under explicit risk rules.

### Evidence
- format_report now outputs status plus six dimensions per stock; JSON decisions include status and dimensions.
- Generated reports/stock_selection_result_2026-06-18.md from real A/HK/US position and trading scans.
- Focused verification passed: 8 agent tests passed after scanner/report changes.

### Commands
- /Users/didi/conda/bin/python -m pytest tests/test_agent_api.py tests/test_agent_snapshot.py tests/test_agent_scanner.py tests/test_stock_agent.py -q
- /Users/didi/conda/bin/python scripts/run_stock_agent.py --symbols A:002475,A:601138,A:688981,A:600036,A:600941,A:300502,A:300308,A:688525,A:300476,A:688347,HK:01024,HK:00700,HK:09988,HK:00005,HK:00981,HK:01347,HK:01810,US:TSM,US:AMD,US:NVDA,US:GOOGL,US:LLY,US:ARM,US:HOOD,US:CRWV,US:IONQ --mode position
- /Users/didi/conda/bin/python scripts/run_stock_agent.py --symbols A:002475,A:601138,A:688981,A:600036,A:600941,A:300502,A:300308,A:688525,A:300476,A:688347,HK:01024,HK:00700,HK:09988,HK:00005,HK:00981,HK:01347,HK:01810,US:TSM,US:AMD,US:NVDA,US:GOOGL,US:LLY,US:ARM,US:HOOD,US:CRWV,US:IONQ --mode trading

### Changed Files Or Artifacts
- src/agent/scanner.py
- tests/test_agent_scanner.py
- reports/stock_selection_result_2026-06-18.md

### Decisions
- Report status labels map verdicts to user-facing actions: buy/staged entry, wait, hold-watch, reduce/protect, avoid.
- The 2026-06-18 run intentionally reported zero direct buy_candidate items because current scores did not clear confirmation gates.

### Blockers And Risks
- Some A-share Eastmoney fund-flow calls returned RemoteDisconnected, so flow dimension can mean missing confirmation rather than verified outflow.

## Run Update - 2026-06-18T09:27:18Z

- Request: `stock-agent-full`
- Summary: Added granular action states, treated missing fund-flow as unconfirmed instead of negative, and stopped after real A/HK/US scan produced actionable stocks.
- Result: actionable stocks found
- Next: Review reports/actionable_stocks_2026-06-18.md; next optional increment is fund-flow reliability and per-market threshold calibration.

### Evidence
- Action states now distinguish buy_now, probe, wait_pullback, wait_breakout, hold_watch, reduce_protect, avoid.
- Real trading scan produced actionable states: 中芯国际 688981 buy_now; 汇丰控股 00005, HOOD, 快手-W 01024, TSM, AMD, LLY, ARM, CRWV probe.
- Generated reports/actionable_stocks_2026-06-18.md and stopped expanding the stock pool after actionable names appeared.
- Focused verification passed: 10 agent tests passed.

### Commands
- /Users/didi/conda/bin/python -m pytest tests/test_stock_agent.py tests/test_agent_scanner.py tests/test_agent_api.py tests/test_agent_snapshot.py -q
- /Users/didi/conda/bin/python scripts/run_stock_agent.py --symbols A:002475,A:601138,A:688981,A:600036,A:600941,A:300502,A:300308,A:688525,A:300476,A:688347,HK:01024,HK:00700,HK:09988,HK:00005,HK:00981,HK:01347,HK:01810,US:TSM,US:AMD,US:NVDA,US:GOOGL,US:LLY,US:ARM,US:HOOD,US:CRWV,US:IONQ --mode trading --json
- /Users/didi/conda/bin/python scripts/run_stock_agent.py --symbols A:002475,A:601138,A:688981,A:600036,A:600941,A:300502,A:300308,A:688525,A:300476,A:688347,HK:01024,HK:00700,HK:09988,HK:00005,HK:00981,HK:01347,HK:01810,US:TSM,US:AMD,US:NVDA,US:GOOGL,US:LLY,US:ARM,US:HOOD,US:CRWV,US:IONQ --mode trading

### Changed Files Or Artifacts
- src/agent/stock_agent.py
- src/agent/scanner.py
- src/agent/__init__.py
- tests/test_stock_agent.py
- tests/test_agent_scanner.py
- reports/actionable_stocks_2026-06-18.md

### Decisions
- Stopped after actionable stocks appeared per user instruction; did not expand to full-market discovery.
- Kept AgentVerdict buckets for compatibility and added ActionState for execution-level status.

### Blockers And Risks
- A-share Eastmoney fund-flow endpoint still intermittently disconnects; current output labels those cases as unconfirmed.

## Run Update - 2026-06-18T10:30:00Z

- Request: `stock-agent-full`
- Summary: 实现回测系统（验证选股逻辑历史胜率），已完成 Task 1-7（股票池、K线预取、事件循环、冷却去重、收益计算、指标聚合、Markdown 报告），6 个单元测试全绿。剩余 Task 8（CLI）+ Task 9（端到端 smoke）。
- Result: implementation in progress (7/9 tasks done)
- Next: 实现 scripts/run_backtest.py CLI 入口，然后跑真实数据端到端 smoke 验证。

### Evidence
- 6 个回测单元测试全绿：prefetch 缓存、事件循环产出信号、冷却去重、收益公式、数据不足处理、指标聚合胜率、报告必含字段。
- 回测直接复用生产代码 StockAgent.evaluate（零逻辑漂移）。
- 测试通过注入 FakeProvider + kline_cache 完全离线，不依赖网络。

### Commands
- /Users/didi/conda/bin/python -m pytest tests/test_backtest_engine.py -q

### Changed Files Or Artifacts
- src/backtest/__init__.py
- src/backtest/universe.py
- src/backtest/engine.py
- src/backtest/results.py
- src/backtest/report.py
- tests/test_backtest_engine.py
- docs/superpowers/specs/2026-06-18-backtest-design.md
- docs/superpowers/plans/2026-06-18-backtest.md

### Decisions
- 方案 A 选定：事件驱动逐日复用 StockAgent，不重写打分逻辑（避免逻辑漂移）。
- 纯持有到期退出（第一版不带止损），避免污染对信号本身的判断。
- 信号冷却：每只股票建仓后 60 交易日内不重复建仓，冷却期内信号忽略（不延迟、不排队）。
- run_backtest 加可选 kline_cache 参数，支持测试注入缓存绕过 DB。
- 成交价用次日开盘，无未来函数；PE/PB/ROE 等基本面字段用最新值，标注为已知偏差（trading 模式权重合计 0.20）。

### Blockers And Risks
- A 股 Eastmoney 资金流接口间歇性断连，回测里这些日期资金维度标 unconfirmed。
- 基本面字段无历史快照，trading 模式权重低但非零，已在报告"已知偏差声明"中标注。

## Run Update - 2026-06-19T11:52:36Z

- Request: `stock-agent-full`
- Summary: Wired stop-loss metrics into the backtest CLI/report path and regenerated the 2025-12-01~2026-06-01 smoke report with stop-loss sections.
- Result: passed
- Next: Next safe increment: calibrate stop-loss thresholds and compare 7% vs disabled/alternate stops on the full 26-symbol two-year universe.

### Evidence
- Backtest CLI now exposes --stop-pct and passes stop_metrics into render_report.
- Focused verification: /Users/didi/conda/bin/python -m pytest tests/test_backtest_engine.py -q -> 10 passed.
- CLI verification: /Users/didi/conda/bin/python scripts/run_backtest.py --help shows --stop-pct.
- Real smoke: 2025-12-01~2026-06-01, A:600036/US:TSM/HK:00700, 390 signals, 3 trades, stop-loss report generated.

### Commands
- /Users/didi/conda/bin/python -m pytest tests/test_backtest_engine.py -q
- /Users/didi/conda/bin/python scripts/run_backtest.py --help
- /Users/didi/conda/bin/python scripts/run_backtest.py --start 2025-12-01 --end 2026-06-01 --mode trading --symbols A:600036,US:TSM,HK:00700 --stop-pct 0.07 --output-dir reports

### Changed Files Or Artifacts
- scripts/run_backtest.py
- src/backtest/report.py
- tests/test_backtest_engine.py
- reports/backtest_result_2025-12-01_2026-06-01.md

### Decisions
- Reports only show stop-loss sections/columns when stop metrics are supplied, preserving legacy report shape when stop-loss is disabled.

### Blockers And Risks
- None.

## Run Update - 2026-06-19T12:01:11Z

- Request: `stock-agent-full`
- Summary: Completed the full 26-symbol two-year stop-loss backtest and verified the generated report.
- Result: passed
- Next: Commit and push the stop-loss backtest/report changes to GitHub.

### Evidence
- Full-pool stop-loss backtest passed: 2024-06-01~2026-06-01, 26 symbols, 13000 signals, 94 cooldown-deduped trades.
- Generated reports/backtest_result_2024-06-01_2026-06-01.md with 7% stop-loss summary: 53/94 trades triggered.
- Focused verification after full run: /Users/didi/conda/bin/python -m pytest tests/test_backtest_engine.py -q -> 10 passed.

### Commands
- /Users/didi/conda/bin/python scripts/run_backtest.py --start 2024-06-01 --end 2026-06-01 --mode trading --stop-pct 0.07 --output-dir reports
- /Users/didi/conda/bin/python -m pytest tests/test_backtest_engine.py -q

### Changed Files Or Artifacts
- reports/backtest_result_2024-06-01_2026-06-01.md

### Decisions
- 7% stop-loss is now included in both small-universe and full-pool reports; next analytical increment can compare multiple stop thresholds.

### Blockers And Risks
- None.

## Run Update - 2026-06-19T12:02:32Z

- Request: `stock-agent-full`
- Summary: Committed stop-loss backtest/report changes locally; push was attempted but blocked by missing GitHub credentials.
- Result: push blocked
- Next: Configure GitHub HTTPS credentials or SSH key, then run git push origin main.

### Evidence
- Local commit created on main; branch is ahead of origin/main by 3 commits.

### Commands
- git commit -m 'feat(backtest): report stop-loss metrics'
- git push origin main

### Changed Files Or Artifacts
- None.

### Decisions
- None.

### Blockers And Risks
- git push origin main failed: fatal: could not read Username for 'https://github.com': Device not configured. SSH also failed with Permission denied (publickey); gh CLI is not installed.
