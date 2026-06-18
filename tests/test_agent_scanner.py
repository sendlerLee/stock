import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import Market
from src.agent import AgentMode, AgentVerdict, StockScanner, StockSnapshot, StockTarget, format_report


class FakeBuilder:
    def build(self, target, days=180):
        if target.symbol == "GOOD":
            return StockSnapshot(
                symbol="GOOD",
                name="Good Co",
                price=20,
                amount=1_000_000_000,
                pe_ttm=10,
                pb=1,
                dividend_yield=5,
                roe=12,
                profit_growth=8,
                revenue_growth=5,
                ma20=19,
                ma60=18,
                rsi14=55,
                flow_5d=1,
                flow_20d=3,
                flow_60d=2,
                sector_change_pct=1,
            )
        return StockSnapshot(
            symbol="BAD",
            name="Bad Co",
            price=8,
            amount=500_000_000,
            pe_ttm=200,
            pb=12,
            ma20=10,
            ma60=11,
            rsi14=35,
            flow_5d=-1,
            flow_20d=-2,
            flow_60d=-3,
            profit_growth=-20,
            sector_change_pct=-3,
        )


def test_scanner_groups_decisions_and_formats_report():
    scanner = StockScanner(builder=FakeBuilder())
    targets = [StockTarget(Market.A, "GOOD"), StockTarget(Market.A, "BAD")]

    result = scanner.scan(targets, mode=AgentMode.POSITION)
    report = format_report(result)

    assert result.buy_candidates[0].symbol == "GOOD"
    assert result.risk_list[0].symbol == "BAD"
    assert result.risk_list[0].verdict in {AgentVerdict.REDUCE, AgentVerdict.AVOID}
    assert "Buy Candidates" in report
    assert "Risk / Avoid" in report
    assert "状态=" in report
    assert "趋势结构=" in report
    assert "估值/分红=" in report
    first = result.to_dict()["buy_candidates"][0]
    assert first["action_state"] in {"buy_now", "probe", "wait_pullback", "wait_breakout"}
    assert first["status"]
    assert first["dimensions"][0]["label"] == "趋势结构"
