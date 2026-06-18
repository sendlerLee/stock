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
    """一笔回测交易（信号触发 → 纯持有到期）。"""

    signal_date: date
    symbol: str
    name: str
    action_state: ActionState
    buy_score: float
    entry_date: date
    entry_price: float
    returns: dict[int, Optional[float]] = field(default_factory=dict)
    # returns[N] = 第 N 个交易日收盘相对 entry_open 的收益；数据不足为 None


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
) -> list[TradeRecord]:
    """把信号序列冷却去重后转为交易列表，算各档窗口收益。

    kline_cache: {cache_key: DataFrame}，key 格式 "MARKET:SYMBOL"。
    """
    trades: list[TradeRecord] = []
    last_entry_idx: dict[str, int] = {}  # symbol → 上次 entry 在其 K 线中的行索引

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
        returns: dict[int, Optional[float]] = {}
        for n in windows:
            exit_i = entry_i + n
            if exit_i >= len(df):
                returns[n] = None
            else:
                exit_close = float(df.iloc[exit_i]["close"])
                returns[n] = round(exit_close / entry_price - 1, 4) if entry_price else None

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
            )
        )
        last_entry_idx[sig.symbol] = entry_i

    return trades
