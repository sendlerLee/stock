#!/usr/bin/env python3
"""回测 CLI：逐日复用 StockAgent，产出胜率报告。

用法：
  python scripts/run_backtest.py --start 2024-06-01 --end 2026-06-01 --mode trading
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.providers import DefaultStockDataProvider, StockTarget
from src.agent.stock_agent import AgentMode
from src.backtest.engine import prefetch_klines, run_backtest
from src.backtest.report import render_report
from src.backtest.results import build_trades, compute_benchmark, compute_metrics
from src.backtest.universe import DEFAULT_BACKTEST_UNIVERSE


def main() -> int:
    parser = argparse.ArgumentParser(description="回测验证选股逻辑历史胜率")
    parser.add_argument("--start", required=True, help="回测开始日期 YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="回测结束日期 YYYY-MM-DD")
    parser.add_argument(
        "--mode", choices=["trading", "position"], default="trading", help="决策模式"
    )
    parser.add_argument("--symbols", help="逗号分隔的 MARKET:SYMBOL 列表，默认用内置池")
    parser.add_argument("--snapshot-days", type=int, default=180, help="snapshot 回看天数")
    parser.add_argument("--stop-pct", type=float, default=0.07, help="止损比例；0 表示禁用止损")
    parser.add_argument("--output-dir", default="reports", help="报告输出目录")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    mode = AgentMode.TRADING if args.mode == "trading" else AgentMode.POSITION

    raw_symbols = args.symbols.split(",") if args.symbols else DEFAULT_BACKTEST_UNIVERSE
    targets = [StockTarget.parse(s) for s in raw_symbols]

    provider = DefaultStockDataProvider()
    print(f"[backtest] 预取 K 线：{len(targets)} 只标的，区间 {start} ~ {end}")
    kline_cache = prefetch_klines(targets, provider, start, end)

    print(f"[backtest] 运行事件循环（mode={mode.value}）...")
    signals = run_backtest(targets, provider, start, end, mode=mode, snapshot_days=args.snapshot_days)
    print(f"[backtest] 产出信号 {len(signals)} 条")

    trades = build_trades(
        signals,
        kline_cache=kline_cache,
        cooldown_days=60,
        stop_pct=args.stop_pct,
    )
    print(f"[backtest] 冷却去重后交易 {len(trades)} 笔")

    metrics = compute_metrics(trades)
    stop_metrics = compute_metrics(trades, use_stop=True) if args.stop_pct > 0 else None
    cache_keys = [f"{t.market.value}:{t.symbol}" for t in targets]
    entry_dates = sorted({tr.entry_date for tr in trades})
    benchmark = compute_benchmark(cache_keys, kline_cache, entry_dates)

    md = render_report(
        start=start, end=end, mode=mode.value, universe_size=len(targets),
        total_signals=len(signals), total_trades=len(trades),
        metrics=metrics, benchmark=benchmark, trades=trades,
        stop_metrics=stop_metrics, stop_pct=args.stop_pct,
    )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"backtest_result_{start}_{end}.md"
    out_file.write_text(md, encoding="utf-8")
    print(f"[backtest] 报告已写出：{out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
