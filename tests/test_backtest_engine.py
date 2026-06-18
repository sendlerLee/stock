import os
import sys
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.backtest.engine import prefetch_klines, SignalRecord, run_backtest


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


def _sample_kline_with_open(n=120):
    """K 线含每日 open/close，从 2024-01-01 起，用于收益计算。"""
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    closes = [10 + i * 0.1 for i in range(n)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": [c - 0.05 for c in closes],
            "high": [c + 0.2 for c in closes],
            "low": [c - 0.2 for c in closes],
            "close": closes,
            "volume": [1000.0] * n,
            "amount": [c * 1000 for c in closes],
        }
    )


def test_run_backtest_produces_signals():
    from src.backtest.engine import run_backtest

    # 构造 90 天温和上行 K 线，使 trend 因子走强
    n = 90
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    closes = [10 + i * 0.2 for i in range(n)]  # 温和上行
    kline = pd.DataFrame(
        {
            "date": dates,
            "open": [c - 0.1 for c in closes],
            "high": [c + 0.3 for c in closes],
            "low": [c - 0.3 for c in closes],
            "close": closes,
            "volume": [2000.0] * n,
            "amount": [c * 2000 for c in closes],
        }
    )
    fake = FakeProvider(kline)
    from config import Market
    from src.agent.providers import StockTarget
    from src.agent.stock_agent import AgentMode

    targets = [StockTarget(Market.A, "000001", name="TEST")]
    # 注入 kline_cache 绕过 DB，避免真实 DB 中的旧数据污染测试
    cache = {"A:000001": kline}
    signals = run_backtest(
        targets,
        provider=fake,
        start=date(2024, 3, 1),
        end=date(2024, 3, 5),
        mode=AgentMode.TRADING,
        kline_cache=cache,
    )

    # 2024-03-01 ~ 03-05 共 5 个交易日，每天 1 个信号
    assert len(signals) == 5
    assert all(s.symbol == "000001" for s in signals)
    assert all(s.mode == AgentMode.TRADING for s in signals)
    # 温和上行趋势 → action_state 应属于可操作类（非 AVOID/REDUCE）
    from src.agent.stock_agent import ActionState

    actionable = {ActionState.BUY_NOW, ActionState.PROBE, ActionState.WAIT_PULLBACK,
                  ActionState.WAIT_BREAKOUT, ActionState.HOLD_WATCH}
    assert all(s.action_state in actionable for s in signals)


def test_cooldown_dedup_one_trade_per_60_days():
    from src.backtest.results import build_trades
    from src.agent.stock_agent import ActionState, AgentVerdict, AgentMode

    # 同一股票连续 30 天 buy_now，冷却窗口 60 天 → 只应产出 1 笔交易
    signals = [
        SignalRecord(
            signal_date=date(2024, 1, d),
            symbol="000001", name="T", market="A",
            mode=AgentMode.TRADING,
            action_state=ActionState.BUY_NOW,
            verdict=AgentVerdict.BUY_CANDIDATE,
            buy_score=80.0, sell_score=10.0,
        )
        for d in range(1, 31)
    ]
    kline = _sample_kline_with_open(120)  # 足够覆盖 60 天窗口
    cache = {"A:000001": kline}

    trades = build_trades(signals, kline_cache=cache, cooldown_days=60, windows=(5, 10, 20, 60))

    assert len(trades) == 1
    assert trades[0].signal_date == date(2024, 1, 1)
