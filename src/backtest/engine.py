"""回测核心：逐日事件循环 + K 线预取缓存。

复用 StockAgent.evaluate 做信号判定（零逻辑漂移）。K 线预取进 data/stock.db，
后续交易日循环从缓存读，避免逐日打网络。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from src.agent.providers import StockDataProvider, StockTarget, AsOfStockDataProvider
from src.agent.snapshot import SnapshotBuilder
from src.agent.stock_agent import AgentMode, AgentVerdict, ActionState, StockAgent
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


def _trading_days(cache: dict[str, pd.DataFrame], start: date, end: date) -> list[date]:
    """取全池 K 线日期并集，落在 [start, end] 内的交易日。"""
    all_dates: set[date] = set()
    for df in cache.values():
        if df.empty:
            continue
        for d in pd.to_datetime(df["date"]).dt.date:
            if start <= d <= end:
                all_dates.add(d)
    return sorted(all_dates)


def run_backtest(
    targets: list[StockTarget],
    provider: StockDataProvider,
    start: date,
    end: date,
    mode: AgentMode = AgentMode.TRADING,
    snapshot_days: int = 180,
    kline_cache: Optional[dict[str, pd.DataFrame]] = None,
) -> list[SignalRecord]:
    """逐日逐股调用 StockAgent.evaluate，返回信号序列。

    每个交易日 t：用 AsOfStockDataProvider(provider, as_of=t) 裁剪数据，
    SnapshotBuilder.build → StockAgent.evaluate → SignalRecord。
    snapshot 构建失败的股票跳过（不中断）。

    kline_cache: 可选的预取缓存，注入后跳过 prefetch_klines（测试用）。
    """
    cache = kline_cache if kline_cache is not None else prefetch_klines(targets, provider, start, end)
    agent = StockAgent()
    signals: list[SignalRecord] = []
    for t in _trading_days(cache, start, end):
        as_of_provider = AsOfStockDataProvider(base=provider, as_of=t)
        builder = SnapshotBuilder(provider=as_of_provider)
        for target in targets:
            try:
                snapshot = builder.build(target, days=snapshot_days)
                decision = agent.evaluate(snapshot, mode)
                signals.append(
                    SignalRecord(
                        signal_date=t,
                        symbol=target.symbol,
                        name=snapshot.name or target.symbol,
                        market=target.market.value,
                        mode=mode,
                        action_state=decision.action_state,
                        verdict=decision.verdict,
                        buy_score=decision.buy_score,
                        sell_score=decision.sell_score,
                    )
                )
            except Exception:
                continue
    return signals
