import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import Market
from src.agent import AsOfStockDataProvider, SnapshotBuilder, StockTarget


def make_kline(n=220, seed=7):
    rng = np.random.default_rng(seed)
    close = 20 + np.linspace(0, 15, n) + rng.normal(0, 0.2, n)
    high = close + 0.5
    low = close - 0.5
    volume = np.linspace(1_000_000, 2_000_000, n)
    return pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=n, freq="B"),
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "amount": close * volume,
        }
    )


class FakeProvider:
    def get_kline(self, target, days=180):
        return make_kline()

    def get_realtime(self, target):
        return {"name": "Fake Bank", "price": 36.0, "change_pct": 1.2, "amount": 1_000_000_000}

    def get_valuation(self, target):
        return {"pe_ttm": 8.0, "pb": 0.9, "dividend_yield": 6.5, "roe": 11.0}

    def get_flow(self, target):
        return {"flow_5d": 3.0, "flow_20d": 8.0, "flow_60d": -2.0}

    def get_sector(self, target):
        return {"sector_change_pct": 1.5, "tags": ["银行", "高股息"], "catalyst_score": 40}


def test_snapshot_builder_merges_provider_data():
    target = StockTarget(market=Market.A, symbol="600000")
    snapshot = SnapshotBuilder(provider=FakeProvider()).build(target)

    assert snapshot.symbol == "600000"
    assert snapshot.name == "Fake Bank"
    assert snapshot.pe_ttm == 8.0
    assert snapshot.pb == 0.9
    assert snapshot.flow_20d == 8.0
    assert snapshot.sector_change_pct == 1.5
    assert snapshot.ma20 is not None
    assert snapshot.ma60 is not None
    assert "银行" in snapshot.tags


def test_as_of_provider_clips_kline_and_derives_close_snapshot():
    class BaseProvider(FakeProvider):
        def get_kline(self, target, days=180):
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-06-16", "2026-06-17", "2026-06-18"]),
                    "open": [10, 11, 12],
                    "high": [11, 12, 13],
                    "low": [9, 10, 11],
                    "close": [10, 11, 12],
                    "volume": [100, 200, 300],
                    "amount": [1000, 2200, 3600],
                }
            )

    target = StockTarget(Market.A, "TEST")
    provider = AsOfStockDataProvider(base=BaseProvider(), as_of=pd.Timestamp("2026-06-17").date())

    kline = provider.get_kline(target, 180)
    realtime = provider.get_realtime(target)

    assert list(kline["close"]) == [10, 11]
    assert realtime["price"] == 11
    assert round(realtime["change_pct"], 2) == 10.0
