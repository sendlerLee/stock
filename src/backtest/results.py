"""信号 → 交易：冷却去重 + 纯持有到期收益。

冷却规则：每只股票建仓后在最长窗口（默认 60 交易日）内不重复建仓；
冷却期内出现的信号忽略（不延迟、不排队）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd

from src.agent.stock_agent import ActionState
from src.backtest.engine import SignalRecord


ENTRY_STATES = {ActionState.BUY_NOW, ActionState.PROBE}
DEFAULT_WINDOWS = (5, 10, 20, 60)


@dataclass
class TradeRecord:
    """一笔回测交易（信号触发 → 纯持有到期 / 可选止损）。

    returns: 纯持有到期收益（对照组），returns[N] = 第 N 日收盘/入场开盘 - 1。
    stop_returns: 止损后收益。止损在第 j 日触发（j < N）时，stop_returns[N] =
        触发日收盘/入场开盘 - 1；未触发则等于 returns[N]。
    stopped_out: 持仓周期内是否触发过止损。
    """

    signal_date: date
    symbol: str
    name: str
    action_state: ActionState
    buy_score: float
    entry_date: date
    entry_price: float
    returns: dict[int, Optional[float]] = field(default_factory=dict)
    stop_returns: dict[int, Optional[float]] = field(default_factory=dict)
    stopped_out: bool = False


def _cache_key(market: str, symbol: str) -> str:
    return f"{market}:{symbol}"


def _bar_index(df: pd.DataFrame) -> dict[date, int]:
    """{日期: 行索引}，用于按交易日定位。"""
    return {d.date(): i for i, d in enumerate(pd.to_datetime(df["date"]))}


def build_trades(
    signals: list[SignalRecord],
    kline_cache: dict[str, pd.DataFrame],
    cooldown_days: int = 60,
    windows: tuple[int, ...] = DEFAULT_WINDOWS,
    stop_pct: float = 0.07,
) -> list[TradeRecord]:
    """把信号序列冷却去重后转为交易列表，算各档窗口收益。

    kline_cache: {cache_key: DataFrame}，key 格式 "MARKET:SYMBOL"。
    stop_pct: 止损比例（相对入场价）。日内最低价跌破 entry_price*(1-stop_pct)
        时触发，以触发日收盘结算。0 表示禁用止损。
    """
    trades: list[TradeRecord] = []
    last_entry_idx: dict[str, int] = {}  # symbol → 上次 entry 在其 K 线中的行索引
    max_window = max(windows)

    for sig in sorted(signals, key=lambda s: s.signal_date):
        if sig.action_state not in ENTRY_STATES:
            continue
        key = _cache_key(sig.market, sig.symbol)
        df = kline_cache.get(key)
        if df is None or df.empty:
            continue
        idx_map = _bar_index(df)
        sig_i = idx_map.get(sig.signal_date)
        if sig_i is None:
            continue
        entry_i = sig_i + 1
        if entry_i >= len(df):
            continue  # 无次日 bar
        # 冷却检查：上次 entry 距今不足 cooldown_days 则跳过
        last = last_entry_idx.get(sig.symbol)
        if last is not None and (entry_i - last) < cooldown_days:
            continue

        entry_date = pd.to_datetime(df.iloc[entry_i]["date"]).date()
        entry_price = float(df.iloc[entry_i]["open"])
        has_low = "low" in df.columns

        # 纯持有到期收益
        returns: dict[int, Optional[float]] = {}
        for n in windows:
            exit_i = entry_i + n
            if exit_i >= len(df):
                returns[n] = None
            else:
                exit_close = float(df.iloc[exit_i]["close"])
                returns[n] = round(exit_close / entry_price - 1, 4) if entry_price else None

        # 止损后收益：在 [entry_i, entry_i+max_window] 内逐 bar 检查 low 跌破止损线
        stop_returns: dict[int, Optional[float]] = {}
        stopped_out = False
        if stop_pct > 0 and entry_price and has_low:
            stop_price = entry_price * (1 - stop_pct)
            stop_exit_i: Optional[int] = None
            scan_end = min(entry_i + max_window, len(df) - 1)
            lows = df["low"].tolist()
            closes = df["close"].tolist()
            for j in range(entry_i, scan_end + 1):
                if float(lows[j]) < stop_price:
                    stop_exit_i = j
                    break
            if stop_exit_i is not None:
                stopped_out = True
                stop_return_val = round(float(closes[stop_exit_i]) / entry_price - 1, 4)
                days_to_stop = stop_exit_i - entry_i
                for n in windows:
                    if n >= days_to_stop:
                        # 窗口覆盖止损触发日 → 用止损收益
                        stop_returns[n] = stop_return_val
                    else:
                        # 窗口短于止损触发日 → 止损未在该窗口内触发，等于纯持有
                        stop_returns[n] = returns.get(n)
            else:
                for n in windows:
                    stop_returns[n] = returns.get(n)
        else:
            for n in windows:
                stop_returns[n] = returns.get(n)

        trades.append(
            TradeRecord(
                signal_date=sig.signal_date,
                symbol=sig.symbol,
                name=sig.name,
                action_state=sig.action_state,
                buy_score=sig.buy_score,
                entry_date=entry_date,
                entry_price=entry_price,
                returns=returns,
                stop_returns=stop_returns,
                stopped_out=stopped_out,
            )
        )
        last_entry_idx[sig.symbol] = entry_i

    return trades


def _window_stats(values: list[float]) -> dict:
    """单档窗口的统计量。"""
    if not values:
        return {"count": 0, "win_rate": None, "mean_return": None,
                "median_return": None, "p25": None, "p75": None}
    wins = sum(1 for v in values if v > 0)
    s = pd.Series(values)
    return {
        "count": len(values),
        "win_rate": round(wins / len(values), 4),
        "mean_return": round(float(s.mean()), 4),
        "median_return": round(float(s.median()), 4),
        "p25": round(float(s.quantile(0.25)), 4),
        "p75": round(float(s.quantile(0.75)), 4),
    }


def compute_metrics(
    trades: list[TradeRecord],
    windows: tuple[int, ...] = DEFAULT_WINDOWS,
    use_stop: bool = False,
) -> dict:
    """按 action_state 分组，算每档窗口胜率/均值/中位/分位/样本量。

    返回 {(group_name, group_value): {window: stats}}。
    group_name 固定 "action_state"；另加 ("benchmark", "signal_equal_weight")。
    use_stop: True 用 stop_returns（止损后），False 用 returns（纯持有）。
    """
    metrics: dict = {}
    source = lambda t: (t.stop_returns if use_stop else t.returns)
    # 按 action_state 分组
    by_state: dict[str, list[TradeRecord]] = {}
    for t in trades:
        by_state.setdefault(t.action_state.value, []).append(t)
    for state, group in by_state.items():
        per_window: dict[int, dict] = {}
        for n in windows:
            vals = [source(t)[n] for t in group if source(t).get(n) is not None]
            per_window[n] = _window_stats(vals)
        metrics[("action_state", state)] = per_window

    # 基准：所有交易等权（信号组自身的等权均值）
    per_window_bench: dict[int, dict] = {}
    for n in windows:
        vals = [source(t)[n] for t in trades if source(t).get(n) is not None]
        per_window_bench[n] = _window_stats(vals)
    metrics[("benchmark", "signal_equal_weight")] = per_window_bench
    return metrics


def compute_benchmark(
    targets_cache_keys: list[str],
    kline_cache: dict[str, pd.DataFrame],
    entry_dates: list[date],
    windows: tuple[int, ...] = DEFAULT_WINDOWS,
) -> dict[int, dict]:
    """等权持有全池基准：每个 entry_date，全池平均 N 日收益。

    用于回答"信号是否跑赢盲选"。
    """
    per_window: dict[int, dict] = {}
    all_returns: dict[int, list[float]] = {n: [] for n in windows}
    for key in targets_cache_keys:
        df = kline_cache.get(key)
        if df is None or df.empty:
            continue
        idx_map = _bar_index(df)
        closes = df["close"].tolist()
        opens = df["open"].tolist()
        for ed in entry_dates:
            ei = idx_map.get(ed)
            if ei is None:
                continue
            ep = float(opens[ei])
            if not ep:
                continue
            for n in windows:
                xi = ei + n
                if xi < len(df):
                    all_returns[n].append(round(closes[xi] / ep - 1, 4))
    for n in windows:
        per_window[n] = _window_stats(all_returns[n])
    return per_window
