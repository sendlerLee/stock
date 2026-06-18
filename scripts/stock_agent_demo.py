import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.agent import AgentMode, StockAgent, StockSnapshot


def sample_universe() -> list[StockSnapshot]:
    return [
        StockSnapshot(
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
            notes=["low valuation, high dividend profile"],
        ),
        StockSnapshot(
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
            notes=["strong trend, valuation risk is high"],
        ),
    ]


def main():
    agent = StockAgent()
    for mode in (AgentMode.POSITION, AgentMode.TRADING):
        print(f"\n=== {mode.value} mode ===")
        decisions = agent.rank(sample_universe(), mode)
        for d in decisions:
            verdict = d.verdict.value
            print(f"{d.symbol} {d.name}: {verdict} buy={d.buy_score:.1f} sell={d.sell_score:.1f} conf={d.confidence}")
            print(f"  action: {d.action}")
            if d.risks.flags:
                print(f"  risks: {'; '.join(d.risks.flags)}")
            print(f"  evidence: {d.evidence[0]}")


if __name__ == "__main__":
    main()
