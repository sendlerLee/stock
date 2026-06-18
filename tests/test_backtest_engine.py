import os
import sys
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.backtest.engine import prefetch_klines, SignalRecord


class FakeProvider:
    """返回固定 K 线，用于离线测试。"""

    def __init__(self, kline: pd.DataFrame):
        self._kline = kline
        self.calls = 0

    def get_kline(self, target, days=180):
        self.calls += 1
        return self._kline.copy()

    def get_realtime(self, target):
        return {}

    def get_valuation(self, target):
        return {}

    def get_flow(self, target):
        return {}

    def get_sector(self, target):
        return {}


def _sample_kline(n=10):
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {
            "date": dates,
            "open": [10.0] * n,
            "high": [11.0] * n,
            "low": [9.0] * n,
            "close": [10.5] * n,
            "volume": [1000.0] * n,
            "amount": [10500.0] * n,
        }
    )


def test_prefetch_klines_caches_to_provider(tmp_path, monkeypatch):
    # 用内存 sqlite，避免污染真实 data/stock.db
    # db.py 在 import 时已 `from config import DB_PATH` 把路径拷进自身命名空间，
    # 所以必须同时 patch db 模块的 DB_PATH，_conn() 才会读到新路径。
    import config
    from src.storage import db as dbmod

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    dbmod.init_db()  # 在新路径建表

    kline = _sample_kline(10)
    fake = FakeProvider(kline)
    from config import Market
    from src.agent.providers import StockTarget

    targets = [StockTarget(Market.A, "000001", name="TEST")]
    cached = prefetch_klines(targets, fake, start=date(2024, 1, 1), end=date(2024, 1, 31))

    assert "A:000001" in cached
    assert len(cached["A:000001"]) == 10
    # 第二次预取应命中 DB 缓存，不再调用 provider.get_kline
    calls_before = fake.calls
    prefetch_klines(targets, fake, start=date(2024, 1, 1), end=date(2024, 1, 31))
    assert fake.calls == calls_before  # DB 命中，未再调网络
