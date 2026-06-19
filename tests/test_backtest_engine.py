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


def test_return_formula_and_insufficient_data():
    from src.backtest.results import build_trades
    from src.agent.stock_agent import ActionState, AgentVerdict, AgentMode

    # K 线：每天 close 递增 1%，open = close（简化定位）
    n = 30
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    closes = [100 * (1.01 ** i) for i in range(n)]
    kline = pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": closes, "low": closes,
            "close": closes,
            "volume": [1000.0] * n, "amount": [c * 1000 for c in closes],
        }
    )
    # 信号在 2024-01-01（idx 0），entry 在 idx 1（01-02）
    signals = [SignalRecord(
        signal_date=date(2024, 1, 1), symbol="000001", name="T", market="A",
        mode=AgentMode.TRADING, action_state=ActionState.PROBE,
        verdict=AgentVerdict.WATCH, buy_score=60.0, sell_score=10.0,
    )]
    cache = {"A:000001": kline}

    trades = build_trades(signals, kline_cache=cache, cooldown_days=60, windows=(5, 10, 20, 60))
    assert len(trades) == 1
    t = trades[0]
    # entry_price = open[idx1] = closes[1] = 101.0
    assert t.entry_price == 101.0
    # return_5 = close[idx6]/open[idx1] - 1 = closes[6]/closes[1] - 1
    expected_5 = closes[6] / closes[1] - 1
    assert abs(t.returns[5] - round(expected_5, 4)) < 1e-6
    # 60 天窗口超出 30 根 bar → None
    assert t.returns[60] is None


def test_metrics_aggregation_win_rate():
    from src.backtest.results import compute_metrics, TradeRecord
    from src.agent.stock_agent import ActionState

    # 4 笔 PROBE 交易，5 天收益：+0.02, +0.01, -0.01, -0.03
    trades = [
        TradeRecord(
            signal_date=date(2024, 1, d), symbol=f"S{d}", name="T",
            action_state=ActionState.PROBE, buy_score=60.0,
            entry_date=date(2024, 1, d + 1), entry_price=100.0,
            returns={5: r, 10: None, 20: None, 60: None},
        )
        for d, r in [(1, 0.02), (2, 0.01), (3, -0.01), (4, -0.03)]
    ]
    metrics = compute_metrics(trades, windows=(5, 10, 20, 60))
    probe5 = metrics[("action_state", ActionState.PROBE.value)][5]
    assert probe5["count"] == 4
    assert probe5["win_rate"] == 0.5  # 2 正 2 负
    assert abs(probe5["mean_return"] - (-0.0025)) < 1e-4


def test_report_contains_required_sections():
    from src.backtest.report import render_report
    from src.backtest.results import TradeRecord
    from src.agent.stock_agent import ActionState

    trades = [
        TradeRecord(
            signal_date=date(2024, 1, 1), symbol="S1", name="T1",
            action_state=ActionState.PROBE, buy_score=60.0,
            entry_date=date(2024, 1, 2), entry_price=100.0,
            returns={5: 0.05, 10: 0.08, 20: None, 60: None},
        ),
        TradeRecord(
            signal_date=date(2024, 1, 3), symbol="S2", name="T2",
            action_state=ActionState.BUY_NOW, buy_score=82.0,
            entry_date=date(2024, 1, 4), entry_price=50.0,
            returns={5: -0.02, 10: 0.01, 20: 0.03, 60: None},
        ),
    ]
    metrics = {
        ("action_state", "probe"): {5: {"count": 1, "win_rate": 1.0, "mean_return": 0.05,
                                         "median_return": 0.05, "p25": 0.05, "p75": 0.05}},
        ("action_state", "buy_now"): {5: {"count": 1, "win_rate": 0.0, "mean_return": -0.02,
                                           "median_return": -0.02, "p25": -0.02, "p75": -0.02}},
        ("benchmark", "signal_equal_weight"): {5: {"count": 2, "win_rate": 0.5,
                                                     "mean_return": 0.015, "median_return": 0.015,
                                                     "p25": 0.015, "p75": 0.015}},
    }
    benchmark = {5: {"count": 26, "win_rate": 0.5, "mean_return": 0.01,
                      "median_return": 0.01, "p25": 0.0, "p75": 0.02}}
    md = render_report(
        start=date(2024, 1, 1), end=date(2024, 6, 1), mode="trading",
        universe_size=26, total_signals=100, total_trades=2,
        metrics=metrics, benchmark=benchmark, trades=trades,
    )
    assert "回测报告" in md
    assert "已知偏差" in md
    assert "未来函数" in md
    assert "buy_now" in md
    assert "probe" in md
    assert "等权基准" in md or "基准" in md
    assert "S1" in md  # 明细


def test_apply_stock_names_fills_empty_names():
    from src.backtest.engine import _apply_stock_names
    from config import Market
    from src.agent.providers import StockTarget

    # 无 name 的 target 应被填充
    t1 = StockTarget(Market.A, "300308")
    t2 = StockTarget(Market.HK, "00700")
    t3 = StockTarget(Market.US, "TSM")
    # 已有 name 的不应被覆盖
    t4 = StockTarget(Market.A, "600036", name="已有名")
    # 未知代码保持空
    t5 = StockTarget(Market.A, "999999")

    _apply_stock_names([t1, t2, t3, t4, t5])

    assert t1.name == "中际旭创"
    assert t2.name == "腾讯控股"
    assert t3.name == "台积电"
    assert t4.name == "已有名"  # 不覆盖
    assert t5.name == ""  # 未知代码保持空


def test_stop_loss_triggered_changes_long_window_returns():
    from src.backtest.results import build_trades
    from src.agent.stock_agent import ActionState, AgentVerdict, AgentMode

    # K 线：入场后第 10 天暴跌到 -8%，之后回升。
    # entry 在 idx1（次日开盘）。
    n = 70
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    closes = [100.0] * n
    # idx 10~12 暴跌（相对 entry_open 100 跌到 ~92，即 -8%）
    for i in range(10, 13):
        closes[i] = 92.0
    lows = closes[:]  # 简化：low = close
    kline = pd.DataFrame(
        {"date": dates, "open": closes, "high": closes, "low": lows, "close": closes,
         "volume": [1000.0] * n, "amount": [c * 1000 for c in closes]}
    )
    signals = [SignalRecord(
        signal_date=date(2024, 1, 1), symbol="000001", name="T", market="A",
        mode=AgentMode.TRADING, action_state=ActionState.PROBE,
        verdict=AgentVerdict.WATCH, buy_score=60.0, sell_score=10.0,
    )]
    cache = {"A:000001": kline}

    trades = build_trades(signals, kline_cache=cache, cooldown_days=60,
                          windows=(5, 10, 20, 60), stop_pct=0.07)
    assert len(trades) == 1
    t = trades[0]
    # 短窗口（5天）：止损未触发，stop_returns 应等于 returns
    assert t.stop_returns[5] == t.returns[5]
    # 长窗口（20/60天）：止损在 idx10 触发，stop_returns 应为止损收益
    expected_stop = round(92.0 / 100.0 - 1, 4)  # -0.08
    assert t.stop_returns[20] == expected_stop
    assert t.stop_returns[60] == expected_stop
    assert t.stopped_out is True


def test_stop_loss_not_triggered_when_price_never_drops():
    from src.backtest.results import build_trades
    from src.agent.stock_agent import ActionState, AgentVerdict, AgentMode

    # K 线一路上涨，永不触发止损
    n = 70
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    closes = [100 + i * 0.5 for i in range(n)]
    kline = pd.DataFrame(
        {"date": dates, "open": closes, "high": closes, "low": closes, "close": closes,
         "volume": [1000.0] * n, "amount": [c * 1000 for c in closes]}
    )
    signals = [SignalRecord(
        signal_date=date(2024, 1, 1), symbol="000001", name="T", market="A",
        mode=AgentMode.TRADING, action_state=ActionState.PROBE,
        verdict=AgentVerdict.WATCH, buy_score=60.0, sell_score=10.0,
    )]
    cache = {"A:000001": kline}

    trades = build_trades(signals, kline_cache=cache, cooldown_days=60,
                          windows=(5, 10, 20, 60), stop_pct=0.07)
    t = trades[0]
    # 未触发止损：所有 stop_returns 应等于 returns
    for n in (5, 10, 20, 60):
        if t.returns.get(n) is not None:
            assert t.stop_returns[n] == t.returns[n]
    assert t.stopped_out is False


def test_stop_loss_disabled_when_stop_pct_zero():
    from src.backtest.results import build_trades
    from src.agent.stock_agent import ActionState, AgentVerdict, AgentMode

    n = 70
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    closes = [100.0] * n
    for i in range(10, 13):
        closes[i] = 50.0  # 暴跌
    kline = pd.DataFrame(
        {"date": dates, "open": closes, "high": closes, "low": closes, "close": closes,
         "volume": [1000.0] * n, "amount": [c * 1000 for c in closes]}
    )
    signals = [SignalRecord(
        signal_date=date(2024, 1, 1), symbol="000001", name="T", market="A",
        mode=AgentMode.TRADING, action_state=ActionState.PROBE,
        verdict=AgentVerdict.WATCH, buy_score=60.0, sell_score=10.0,
    )]
    cache = {"A:000001": kline}

    trades = build_trades(signals, kline_cache=cache, cooldown_days=60,
                          windows=(5, 10, 20, 60), stop_pct=0.0)
    t = trades[0]
    # stop_pct=0 禁用止损：stop_returns 全部等于 returns
    for n in (5, 10, 20, 60):
        assert t.stop_returns.get(n) == t.returns.get(n)
    assert t.stopped_out is False
