"""
动量类指标：RSI, KDJ, BIAS
"""
import pandas as pd
import numpy as np


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    RSI（相对强弱指数）
    Wilder's smoothing（等同于 EMA span=2*period-1）
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder smoothing
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def kdj(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 9,
    signal_k: int = 3,
    signal_d: int = 3,
) -> pd.DataFrame:
    """
    KDJ 随机指标
    返回 DataFrame，列：K, D, J
    """
    lowest_low = low.rolling(window=period, min_periods=period).min()
    highest_high = high.rolling(window=period, min_periods=period).max()

    rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
    rsv = rsv.fillna(50)  # 无法计算时默认 50

    K = rsv.ewm(alpha=1 / signal_k, adjust=False).mean()
    D = K.ewm(alpha=1 / signal_d, adjust=False).mean()
    J = 3 * K - 2 * D

    return pd.DataFrame({"kdj_k": K, "kdj_d": D, "kdj_j": J})


def bias(series: pd.Series, period: int = 20) -> pd.Series:
    """
    BIAS 乖离率 = (close - MAn) / MAn * 100
    """
    ma_n = series.rolling(window=period, min_periods=period).mean()
    return (series - ma_n) / ma_n * 100


def add_momentum_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    追加动量指标列：
      rsi6, rsi14
      kdj_k, kdj_d, kdj_j
      bias6, bias12, bias24
    """
    df = df.copy()

    df["rsi6"] = rsi(df["close"], 6)
    df["rsi14"] = rsi(df["close"], 14)

    kdj_df = kdj(df["high"], df["low"], df["close"])
    df = pd.concat([df, kdj_df], axis=1)

    df["bias6"] = bias(df["close"], 6)
    df["bias12"] = bias(df["close"], 12)
    df["bias24"] = bias(df["close"], 24)

    return df
