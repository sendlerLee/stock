"""信号生成单元测试"""
import pytest
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.indicators import add_all_indicators
from src.strategy.signals import ma_crossover, macd_crossover, rsi_threshold


def make_df(n=200, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 10 + np.cumsum(rng.normal(0, 0.5, n))
    high  = close + rng.uniform(0.1, 0.5, n)
    low   = close - rng.uniform(0.1, 0.5, n)
    vol   = rng.integers(100_000, 1_000_000, n).astype(float)
    dates = pd.date_range("2022-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "date": dates, "open": close, "high": high, "low": low,
        "close": close, "volume": vol, "amount": close * vol,
    })


def test_ma_signal_values():
    df = add_all_indicators(make_df())
    sig = ma_crossover(df)
    assert set(sig.unique()).issubset({-1, 0, 1})


def test_macd_signal_values():
    df = add_all_indicators(make_df())
    sig = macd_crossover(df)
    assert set(sig.unique()).issubset({-1, 0, 1})


def test_rsi_signal_values():
    df = add_all_indicators(make_df())
    sig = rsi_threshold(df)
    assert set(sig.unique()).issubset({-1, 0, 1})


def test_signal_length():
    df = add_all_indicators(make_df())
    assert len(ma_crossover(df)) == len(df)
