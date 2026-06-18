"""
信号生成模块
输入带指标列的 DataFrame，输出 signal 列：1=买入, -1=卖出, 0=持仓
"""
import pandas as pd
import numpy as np


def ma_crossover(
    df: pd.DataFrame,
    fast_col: str = "ma5",
    slow_col: str = "ma20",
) -> pd.Series:
    """
    MA 金叉死叉信号
    金叉（快线上穿慢线）→ 买入(1)
    死叉（快线下穿慢线）→ 卖出(-1)
    """
    fast = df[fast_col]
    slow = df[slow_col]
    prev_fast = fast.shift(1)
    prev_slow = slow.shift(1)

    buy  = (prev_fast <= prev_slow) & (fast > slow)
    sell = (prev_fast >= prev_slow) & (fast < slow)

    signal = pd.Series(0, index=df.index)
    signal[buy] = 1
    signal[sell] = -1
    return signal


def macd_crossover(df: pd.DataFrame) -> pd.Series:
    """
    MACD 金叉死叉信号（MACD 线与信号线的交叉）
    """
    macd_line   = df["macd"]
    signal_line = df["macd_signal"]
    prev_macd   = macd_line.shift(1)
    prev_sig    = signal_line.shift(1)

    buy  = (prev_macd <= prev_sig) & (macd_line > signal_line)
    sell = (prev_macd >= prev_sig) & (macd_line < signal_line)

    signal = pd.Series(0, index=df.index)
    signal[buy] = 1
    signal[sell] = -1
    return signal


def rsi_threshold(
    df: pd.DataFrame,
    rsi_col: str = "rsi14",
    oversold: float = 30.0,
    overbought: float = 70.0,
) -> pd.Series:
    """
    RSI 超买超卖信号
    RSI 从超卖区回升穿过 oversold → 买入
    RSI 从超买区回落穿过 overbought → 卖出
    """
    rsi = df[rsi_col]
    prev_rsi = rsi.shift(1)

    buy  = (prev_rsi <= oversold) & (rsi > oversold)
    sell = (prev_rsi >= overbought) & (rsi < overbought)

    signal = pd.Series(0, index=df.index)
    signal[buy] = 1
    signal[sell] = -1
    return signal


def bollinger_breakout(df: pd.DataFrame) -> pd.Series:
    """
    布林带突破信号
    价格上穿上轨 → 卖出（超买）
    价格下穿下轨 → 买入（超卖回归）
    """
    close = df["close"]
    upper = df["bb_upper"]
    lower = df["bb_lower"]
    prev_close = close.shift(1)

    buy  = (prev_close >= lower) & (close < lower)   # 跌破下轨
    sell = (prev_close <= upper) & (close > upper)   # 突破上轨

    signal = pd.Series(0, index=df.index)
    signal[buy] = 1
    signal[sell] = -1
    return signal


# ── 复合信号 ──────────────────────────────────────────────────────────
def composite_signal(
    df: pd.DataFrame,
    weights: dict | None = None,
) -> pd.Series:
    """
    多策略加权投票信号（取整数：1/-1/0）
    默认权重：ma_crossover=0.4, macd=0.3, rsi=0.3
    """
    if weights is None:
        weights = {"ma": 0.4, "macd": 0.3, "rsi": 0.3}

    composite = pd.Series(0.0, index=df.index)
    if "ma" in weights:
        composite += weights["ma"] * ma_crossover(df)
    if "macd" in weights:
        composite += weights["macd"] * macd_crossover(df)
    if "rsi" in weights:
        composite += weights["rsi"] * rsi_threshold(df)

    # 阈值化：>0.2 → 买，<-0.2 → 卖
    signal = pd.Series(0, index=df.index)
    signal[composite > 0.2] = 1
    signal[composite < -0.2] = -1
    return signal
