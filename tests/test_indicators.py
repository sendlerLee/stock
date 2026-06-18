"""技术指标单元测试"""
import pytest
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.indicators.trend import ma, ema, macd, bollinger_bands, add_trend_indicators
from src.indicators.momentum import rsi, kdj, add_momentum_indicators
from src.indicators.volume import obv, add_volume_indicators


def make_df(n=100, seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 10 + np.cumsum(rng.normal(0, 0.5, n))
    high  = close + rng.uniform(0.1, 0.5, n)
    low   = close - rng.uniform(0.1, 0.5, n)
    open_ = close + rng.normal(0, 0.2, n)
    vol   = rng.integers(100_000, 1_000_000, n).astype(float)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "date": dates, "open": open_, "high": high, "low": low,
        "close": close, "volume": vol, "amount": close * vol,
    })


class TestMA:
    def test_length(self):
        df = make_df()
        result = ma(df["close"], 5)
        assert len(result) == len(df)

    def test_first_valid(self):
        df = make_df()
        result = ma(df["close"], 5)
        assert pd.isna(result.iloc[3])   # 前4行应为 NaN（min_periods=period）
        assert not pd.isna(result.iloc[4])

    def test_manual_check(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = ma(s, 3)
        assert abs(result.iloc[4] - 4.0) < 1e-9


class TestMACD:
    def test_columns(self):
        df = make_df()
        result = macd(df["close"])
        assert set(result.columns) == {"macd", "macd_signal", "macd_hist"}

    def test_hist_equals_diff(self):
        df = make_df()
        result = macd(df["close"])
        diff = (result["macd"] - result["macd_signal"] - result["macd_hist"]).abs()
        assert diff.max() < 1e-9


class TestRSI:
    def test_range(self):
        df = make_df()
        result = rsi(df["close"], 14).dropna()
        assert (result >= 0).all() and (result <= 100).all()

    def test_length(self):
        df = make_df()
        assert len(rsi(df["close"], 14)) == len(df)


class TestKDJ:
    def test_columns(self):
        df = make_df()
        result = kdj(df["high"], df["low"], df["close"])
        assert {"kdj_k", "kdj_d", "kdj_j"}.issubset(result.columns)

    def test_k_range(self):
        df = make_df(200)
        k = kdj(df["high"], df["low"], df["close"])["kdj_k"].dropna()
        assert (k >= 0).all() and (k <= 100).all()


class TestOBV:
    def test_length(self):
        df = make_df()
        result = obv(df["close"], df["volume"])
        assert len(result) == len(df)

    def test_trend(self):
        # 价格一直上涨时 OBV 应持续增加
        close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        vol   = pd.Series([1000.0] * 5)
        result = obv(close, vol)
        assert result.is_monotonic_increasing


class TestAddAll:
    def test_add_trend(self):
        df = make_df()
        result = add_trend_indicators(df)
        for col in ["ma5", "ma20", "macd", "bb_upper"]:
            assert col in result.columns

    def test_add_momentum(self):
        df = make_df()
        result = add_momentum_indicators(df)
        for col in ["rsi14", "kdj_k", "bias6"]:
            assert col in result.columns

    def test_add_volume(self):
        df = make_df()
        result = add_volume_indicators(df)
        for col in ["obv", "vwap", "vol_ma5"]:
            assert col in result.columns

    def test_no_side_effect(self):
        df = make_df()
        original_cols = list(df.columns)
        add_trend_indicators(df)
        assert list(df.columns) == original_cols  # 原始 df 未被修改
