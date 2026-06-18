"""
回测引擎封装（基于 backtrader）
提供简洁的入口 run_backtest()，返回结构化结果
"""
from __future__ import annotations
from typing import Callable
import io

import pandas as pd
import numpy as np
import backtrader as bt
import backtrader.analyzers as btanalyzers


# ── 通用策略 ──────────────────────────────────────────────────────────
class SignalStrategy(bt.Strategy):
    """
    接收外部信号序列（+1 买 / -1 卖 / 0 持有）的通用策略。
    信号通过 params.signal_series 传入（与 data feed 行数对应）。
    """
    params = (
        ("signal_series", None),
        ("stake", 100),           # 每次交易股数
        ("commission", 0.001),    # 手续费
    )

    def __init__(self):
        self._signals = self.p.signal_series
        self._idx = 0

    def next(self):
        if self._signals is None or self._idx >= len(self._signals):
            return
        sig = self._signals.iloc[self._idx]
        self._idx += 1

        if sig == 1 and not self.position:
            self.buy(size=self.p.stake)
        elif sig == -1 and self.position:
            self.sell(size=self.p.stake)


# ── 数据 Feed ─────────────────────────────────────────────────────────
class PandasFeed(bt.feeds.PandasData):
    params = (
        ("datetime", None),
        ("open",   "open"),
        ("high",   "high"),
        ("low",    "low"),
        ("close",  "close"),
        ("volume", "volume"),
        ("openinterest", -1),
    )


def _df_to_feed(df: pd.DataFrame) -> PandasFeed:
    """将标准 DataFrame 转为 backtrader 数据源"""
    _df = df.set_index("date")[["open", "high", "low", "close", "volume"]].copy()
    _df.index = pd.to_datetime(_df.index)
    return PandasFeed(dataname=_df)


# ── 主入口 ────────────────────────────────────────────────────────────
def run_backtest(
    df: pd.DataFrame,
    signal: pd.Series,
    initial_cash: float = 100_000.0,
    commission: float = 0.001,
    stake: int = 100,
) -> dict:
    """
    Parameters
    ----------
    df      : 带 date/open/high/low/close/volume 列的 DataFrame
    signal  : 与 df 等长的信号序列（1/-1/0）
    initial_cash : 初始资金
    commission   : 双边手续费率
    stake        : 每次买卖股数

    Returns
    -------
    dict
        final_value   最终资产
        total_return  总收益率（%）
        annual_return 年化收益率（%）
        sharpe_ratio  夏普比率
        max_drawdown  最大回撤（%）
        win_rate      胜率（%）
        trade_count   总交易次数
        equity_curve  每日资产序列（dict: date→value）
    """
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=commission)

    feed = _df_to_feed(df)
    cerebro.adddata(feed)

    cerebro.addstrategy(
        SignalStrategy,
        signal_series=signal,
        stake=stake,
        commission=commission,
    )

    # 分析器
    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="sharpe", riskfreerate=0.03, annualize=True)
    cerebro.addanalyzer(btanalyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(btanalyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(btanalyzers.TimeReturn, _name="time_return")

    results = cerebro.run()
    strat = results[0]

    final_value = cerebro.broker.getvalue()
    total_return = (final_value - initial_cash) / initial_cash * 100

    # 年化（按实际天数）
    n_days = (df["date"].iloc[-1] - df["date"].iloc[0]).days
    annual_return = ((1 + total_return / 100) ** (365 / max(n_days, 1)) - 1) * 100

    # 夏普
    sharpe_analysis = strat.analyzers.sharpe.get_analysis()
    sharpe = sharpe_analysis.get("sharperatio") or 0.0

    # 最大回撤
    dd_analysis = strat.analyzers.drawdown.get_analysis()
    max_drawdown = dd_analysis.get("max", {}).get("drawdown", 0.0)

    # 胜率
    trade_analysis = strat.analyzers.trades.get_analysis()
    won   = trade_analysis.get("won", {}).get("total", 0)
    lost  = trade_analysis.get("lost", {}).get("total", 0)
    total = won + lost
    win_rate = (won / total * 100) if total > 0 else 0.0

    # 资产曲线
    tr = strat.analyzers.time_return.get_analysis()
    equity: dict[str, float] = {}
    cumulative = initial_cash
    for dt, ret in tr.items():
        cumulative *= (1 + ret)
        equity[str(dt.date())] = round(cumulative, 2)

    return {
        "final_value": round(final_value, 2),
        "total_return": round(total_return, 2),
        "annual_return": round(annual_return, 2),
        "sharpe_ratio": round(float(sharpe), 4),
        "max_drawdown": round(float(max_drawdown), 2),
        "win_rate": round(win_rate, 2),
        "trade_count": total,
        "equity_curve": equity,
    }
