import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.agent import ActionState, AgentMode, AgentVerdict, StockAgent, StockSnapshot


def test_position_candidate_for_low_valuation_dividend_stock():
    snapshot = StockSnapshot(
        symbol="600036",
        name="招商银行",
        market="A",
        price=37.44,
        change_pct=-2.07,
        amount=1_935_200_000,
        pe_ttm=6.26,
        pb=0.83,
        dividend_yield=8.0,
        roe=12.0,
        revenue_growth=3.8,
        profit_growth=1.5,
        ma20=36.0,
        ma60=35.2,
        rsi14=58.0,
        volume_ratio=1.23,
        flow_5d=8.1,
        flow_20d=22.1,
        flow_60d=-20.8,
        sector_change_pct=-2.08,
        tags=["银行", "高股息", "沪股通"],
    )

    decision = StockAgent().evaluate(snapshot, AgentMode.POSITION)

    assert decision.verdict in {AgentVerdict.BUY_CANDIDATE, AgentVerdict.WATCH}
    assert decision.buy_score > decision.sell_score
    assert any("dividend_yield=8.00" in line for line in decision.evidence)


def test_trading_candidate_keeps_high_valuation_risk_visible():
    snapshot = StockSnapshot(
        symbol="688347",
        name="华虹宏力",
        market="A",
        price=286.98,
        change_pct=10.08,
        amount=6_011_600_563,
        pe_ttm=893.29,
        pb=11.02,
        revenue_growth=20.0,
        profit_growth=8.0,
        ma20=220.0,
        ma60=180.0,
        rsi14=78.0,
        volume_ratio=2.4,
        flow_5d=22.0,
        flow_20d=21.2,
        flow_60d=-1.0,
        sector_change_pct=4.71,
        catalyst_score=75.0,
        tags=["集成电路制造", "半导体", "国产替代", "存储芯片"],
    )

    decision = StockAgent().evaluate(snapshot, AgentMode.TRADING)

    assert decision.verdict in {AgentVerdict.BUY_CANDIDATE, AgentVerdict.WATCH}
    assert decision.risks.score > 0
    assert any("PE TTM very high" in flag for flag in decision.risks.flags)
    assert any("PB very high" in flag for flag in decision.risks.flags)


def test_broken_trend_and_negative_flow_reduce():
    snapshot = StockSnapshot(
        symbol="TEST",
        name="Weak Co",
        price=8.0,
        change_pct=-3.2,
        amount=200_000_000,
        pe_ttm=80.0,
        pb=5.0,
        profit_growth=-20.0,
        ma20=10.0,
        ma60=12.0,
        rsi14=38.0,
        flow_5d=-2.0,
        flow_20d=-8.0,
        flow_60d=-15.0,
        sector_change_pct=-2.5,
    )

    decision = StockAgent().evaluate(snapshot, AgentMode.TRADING)

    assert decision.verdict == AgentVerdict.REDUCE
    assert decision.sell_score >= 65


def test_trading_strong_setup_can_be_actionable_probe():
    snapshot = StockSnapshot(
        symbol="HOT",
        name="Hot Trend",
        price=102.0,
        change_pct=3.0,
        amount=2_000_000_000,
        pe_ttm=70.0,
        pb=6.0,
        revenue_growth=25.0,
        ma20=100.0,
        ma60=82.0,
        rsi14=62.0,
        volume_ratio=1.6,
        flow_5d=None,
        flow_20d=None,
        flow_60d=None,
        sector_change_pct=3.5,
        catalyst_score=80.0,
        tags=["AI", "半导体"],
    )

    decision = StockAgent().evaluate(snapshot, AgentMode.TRADING)

    assert decision.action_state in {ActionState.BUY_NOW, ActionState.PROBE}
    assert decision.verdict in {AgentVerdict.BUY_CANDIDATE, AgentVerdict.WATCH}
    assert any("status=unconfirmed" in line for line in decision.evidence)


def test_extended_trading_setup_waits_for_pullback():
    snapshot = StockSnapshot(
        symbol="EXT",
        name="Extended Trend",
        price=126.0,
        amount=2_000_000_000,
        pe_ttm=80.0,
        pb=7.0,
        ma20=100.0,
        ma60=75.0,
        rsi14=74.0,
        volume_ratio=1.5,
        sector_change_pct=3.0,
        catalyst_score=80.0,
        tags=["AI"],
    )

    decision = StockAgent().evaluate(snapshot, AgentMode.TRADING)

    assert decision.action_state == ActionState.WAIT_PULLBACK
