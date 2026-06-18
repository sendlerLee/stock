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
