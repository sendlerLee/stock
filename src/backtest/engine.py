"""回测核心：逐日事件循环 + K 线预取缓存。

复用 StockAgent.evaluate 做信号判定（零逻辑漂移）。K 线预取进 data/stock.db，
后续交易日循环从缓存读，避免逐日打网络。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from src.agent.providers import StockDataProvider, StockTarget
from src.agent.stock_agent import AgentMode, AgentVerdict, ActionState
from src.storage import db as dbmod


@dataclass(frozen=True)
class SignalRecord:
    """单个交易日对单只股票的信号判定结果。"""

    signal_date: date
    symbol: str
    name: str
    market: str
    mode: AgentMode
    action_state: ActionState
    verdict: AgentVerdict
    buy_score: float
    sell_score: float


def _cache_key(target: StockTarget) -> str:
    return f"{target.market.value}:{target.symbol}"


def prefetch_klines(
    targets: list[StockTarget],
    provider: StockDataProvider,
    start: date,
    end: date,
) -> dict[str, pd.DataFrame]:
    """预取全池 K 线写入 data/stock.db，并返回内存缓存。

    已有缓存的股票不重复拉取（幂等）。返回 {cache_key: DataFrame}，
    DataFrame 按 date 升序、含列 date/open/high/low/close/volume/amount。
    """
    cache: dict[str, pd.DataFrame] = {}
    days_span = (end - start).days + 180  # 多取 180 天保证指标 warmup
    for target in targets:
        key = _cache_key(target)
        df = dbmod.query_kline(
            target.symbol,
            market=target.market.value,
            start=start.isoformat(),
            end=end.isoformat(),
        )
        if df.empty:
            try:
                fetched = provider.get_kline(target, days=days_span)
            except Exception:
                fetched = pd.DataFrame()
            if not fetched.empty:
                dbmod.upsert_kline(fetched, target.symbol, target.market.value)
                df = fetched.copy()
        if not df.empty:
            df = df.sort_values("date").reset_index(drop=True)
            df["date"] = pd.to_datetime(df["date"])
        cache[key] = df
    return cache
