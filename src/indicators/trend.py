"""
趋势类指标：MA, MACD, Bollinger Bands
输入 df 需包含 close 列（float64），date 列可选
所有函数均返回原 df 的副本，追加新列，不修改原始 df
"""
import pandas as pd
import numpy as np


def ma(series: pd.Series, period: int) -> pd.Series:
    """简单移动平均"""
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """指数移动平均"""
    return series.ewm(span=period, adjust=False).mean()


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """
    MACD 指标
    返回 DataFrame，列：macd, signal_line, histogram
    """
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({
        "macd": macd_line,
        "macd_signal": signal_line,
        "macd_hist": histogram,
    })


def bollinger_bands(
    series: pd.Series,
    period: int = 20,
    std_dev: float = 2.0,
) -> pd.DataFrame:
    """
    布林带
    返回 DataFrame，列：bb_upper, bb_mid, bb_lower, bb_width
    """
    mid = series.rolling(window=period, min_periods=period).mean()
    std = series.rolling(window=period, min_periods=period).std(ddof=0)
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    width = (upper - lower) / mid  # 带宽（百分比）
    return pd.DataFrame({
        "bb_upper": upper,
        "bb_mid": mid,
        "bb_lower": lower,
        "bb_width": width,
    })


def add_trend_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    在 df 上追加所有趋势指标列：
      ma5, ma10, ma20, ma60
      macd, macd_signal, macd_hist
      bb_upper, bb_mid, bb_lower, bb_width
    """
    df = df.copy()
    close = df["close"]

    # 均线
    for p in [5, 10, 20, 60]:
        df[f"ma{p}"] = ma(close, p)

    # MACD
    macd_df = macd(close)
    df = pd.concat([df, macd_df], axis=1)

    # 布林带
    bb_df = bollinger_bands(close)
    df = pd.concat([df, bb_df], axis=1)

    return df
