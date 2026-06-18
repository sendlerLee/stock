"""
量能类指标：OBV, VWAP, 成交量均线
"""
import pandas as pd
import numpy as np


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    OBV（能量潮）
    收盘上涨累加成交量，下跌累减
    """
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    direction.iloc[0] = 0
    return (direction * volume).cumsum()


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    VWAP（成交量加权平均价）
    使用典型价格 (H+L+C)/3
    注意：标准 VWAP 每日重置，此处提供累计版（适用回测）
    """
    typical = (high + low + close) / 3
    cum_vol = volume.cumsum()
    cum_tp_vol = (typical * volume).cumsum()
    return cum_tp_vol / cum_vol


def vol_ma(volume: pd.Series, period: int = 5) -> pd.Series:
    """成交量移动平均"""
    return volume.rolling(window=period, min_periods=period).mean()


def add_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    追加量能指标列：
      obv
      vwap（累计）
      vol_ma5, vol_ma10
    """
    df = df.copy()

    df["obv"] = obv(df["close"], df["volume"])
    df["vwap"] = vwap(df["high"], df["low"], df["close"], df["volume"])
    df["vol_ma5"] = vol_ma(df["volume"], 5)
    df["vol_ma10"] = vol_ma(df["volume"], 10)

    return df
