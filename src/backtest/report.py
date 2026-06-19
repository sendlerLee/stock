"""回测 Markdown 报告生成。"""
from __future__ import annotations

from datetime import date
from typing import Optional

from src.backtest.results import TradeRecord


def _fmt_stat(stats: Optional[dict]) -> str:
    if not stats or stats.get("count", 0) == 0:
        return "-"
    return (
        f"胜率{stats['win_rate']:.0%}/均值{stats['mean_return']:+.2%}/"
        f"中位{stats['median_return']:+.2%}/n={stats['count']}"
    )


def render_report(
    start: date,
    end: date,
    mode: str,
    universe_size: int,
    total_signals: int,
    total_trades: int,
    metrics: dict,
    benchmark: dict,
    trades: list[TradeRecord],
    windows: tuple[int, ...] = (5, 10, 20, 60),
    stop_metrics: Optional[dict] = None,
    stop_pct: float = 0.0,
) -> str:
    """生成回测 Markdown 报告。

    stop_metrics: 止损后的分组指标（compute_metrics(use_stop=True)）。为 None 则不显示止损列。
    stop_pct: 止损比例，>0 时在元信息标注。
    """
    show_stop = bool(stop_metrics and stop_pct > 0)
    lines: list[str] = []
    lines.append(f"# 回测报告 ({mode} 模式)")
    lines.append("")
    lines.append("## 1. 元信息")
    lines.append("")
    lines.append(f"- 区间：{start} ~ {end}")
    lines.append(f"- 模式：{mode}")
    lines.append(f"- 股票池规模：{universe_size}")
    lines.append(f"- 总信号数：{total_signals}")
    lines.append(f"- 总交易数（冷却去重后）：{total_trades}")
    lines.append(f"- 评估窗口：{list(windows)} 天")
    if stop_pct > 0:
        stopped_count = sum(1 for t in trades if t.stopped_out)
        lines.append(f"- 止损规则：入场价 × (1 - {stop_pct:.0%})，触发 {stopped_count}/{total_trades} 笔")
    lines.append("")

    header = " | ".join(f"{n}天" for n in windows)

    lines.append("## 2. 分组胜率主表（纯持有到期）")
    lines.append("")
    lines.append(f"| 分组 | {header} |")
    lines.append("|" + "---|" * (len(windows) + 1))
    for (group, value), per_window in metrics.items():
        if group == "benchmark":
            continue
        cells = " | ".join(_fmt_stat(per_window.get(n)) for n in windows)
        lines.append(f"| {value} | {cells} |")
    lines.append("")

    next_section = 3
    if show_stop:
        lines.append("## 3. 分组胜率主表（止损后）")
        lines.append("")
        lines.append(f"| 分组 | {header} |")
        lines.append("|" + "---|" * (len(windows) + 1))
        for (group, value), per_window in stop_metrics.items():
            if group == "benchmark":
                continue
            cells = " | ".join(_fmt_stat(per_window.get(n)) for n in windows)
            lines.append(f"| {value} | {cells} |")
        lines.append("")
        next_section = 4

    lines.append(f"## {next_section}. 基准对照")
    lines.append("")
    lines.append('**等权持有全池基准**（回答"信号是否跑赢盲选"）：')
    lines.append("")
    lines.append("| 分组 | " + header + " |")
    lines.append("|" + "---|" * (len(windows) + 1))
    bench_cells = " | ".join(_fmt_stat(benchmark.get(n)) for n in windows)
    lines.append(f"| 等权基准 | {bench_cells} |")
    sig_bench = metrics.get(("benchmark", "signal_equal_weight"), {})
    sig_cells = " | ".join(_fmt_stat(sig_bench.get(n)) for n in windows)
    lines.append(f"| 信号组等权 | {sig_cells} |")
    if show_stop:
        sig_stop_bench = stop_metrics.get(("benchmark", "signal_equal_weight"), {})
        sig_stop_cells = " | ".join(_fmt_stat(sig_stop_bench.get(n)) for n in windows)
        lines.append(f"| 信号组等权(止损后) | {sig_stop_cells} |")
    lines.append("")

    next_section += 1
    lines.append(f"## {next_section}. 明细样本")
    lines.append("")

    def avg_return(t: TradeRecord) -> float:
        vals = [v for v in t.returns.values() if v is not None]
        return sum(vals) / len(vals) if vals else 0.0

    sorted_trades = sorted(trades, key=avg_return, reverse=True)
    lines.append("**收益前 5**：")
    lines.append("")
    lines.append(_trade_header(windows, show_stop))
    lines.append(_trade_separator(windows, show_stop))
    for t in sorted_trades[:5]:
        lines.append(_trade_row(t, windows, show_stop))
    lines.append("")
    lines.append("**收益后 5**：")
    lines.append("")
    lines.append(_trade_header(windows, show_stop))
    lines.append(_trade_separator(windows, show_stop))
    for t in sorted_trades[-5:]:
        lines.append(_trade_row(t, windows, show_stop))
    lines.append("")

    next_section += 1
    lines.append(f"## {next_section}. 已知偏差声明")
    lines.append("")
    lines.append("- ✅ **无未来函数**：趋势/MA/RSI/量比、A股资金流——用 as-of 真实历史值。")
    lines.append("- ⚠️ **有未来函数**：PE/PB/ROE/分红/行业题材——免费接口只返回最新值，")
    lines.append('  回测用的是"今天的值"而非"信号日的值"。trading 模式下 fundamental(0.10)+valuation(0.10) 权重合计 0.20，影响有限但非零。')
    lines.append("- ✅ 成交价用次日开盘，信号日所有指标已确定，无未来函数。")
    lines.append("- 冷却期内信号被忽略（不延迟、不排队），每只股票 60 交易日内最多一单。")
    if show_stop:
        lines.append("- 止损用触发日收盘价结算（保守假设，不假设精确止损价成交）。")
    lines.append("")

    return "\n".join(lines)


def _trade_header(windows: tuple[int, ...], show_stop: bool) -> str:
    columns = ["标的", "信号日", "状态", *[f"{n}天" for n in windows]]
    if show_stop:
        columns.append("止损")
    return "| " + " | ".join(columns) + " |"


def _trade_separator(windows: tuple[int, ...], show_stop: bool) -> str:
    column_count = 3 + len(windows) + (1 if show_stop else 0)
    return "|" + "---|" * column_count


def _trade_row(t: TradeRecord, windows: tuple[int, ...], show_stop: bool) -> str:
    cells = []
    for n in windows:
        v = t.returns.get(n)
        cells.append(f"{v:+.2%}" if v is not None else "-")
    row = f"| {t.symbol} {t.name} | {t.signal_date} | {t.action_state.value} | " + " | ".join(cells)
    if show_stop:
        stop_flag = "✓触发" if t.stopped_out else "-"
        row += f" | {stop_flag}"
    return row + " |"
