import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient

from src.agent import AgentMode, StockAgent, StockSnapshot
from src.api.main import app
from src.api.routers import agent as agent_router


class FakeScanner:
    def scan(self, targets, mode=AgentMode.TRADING, days=180):
        decision = StockAgent().evaluate(
            StockSnapshot(
                symbol=targets[0].symbol,
                name="Fake",
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
            ),
            mode,
        )

        class Result:
            def to_dict(self):
                return {
                    "mode": mode.value,
                    "buy_candidates": [{"symbol": decision.symbol, "verdict": decision.verdict.value}],
                    "watchlist": [],
                    "risk_list": [],
                    "errors": [],
                }

        return Result()


def test_agent_scan_endpoint(monkeypatch):
    monkeypatch.setattr(agent_router, "StockScanner", lambda: FakeScanner())
    client = TestClient(app)

    resp = client.post("/agent/scan", json={"symbols": ["A:600036"], "mode": "position", "days": 180})

    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "position"
    assert body["buy_candidates"][0]["symbol"] == "600036"


def test_agent_scan_rejects_bad_symbol(monkeypatch):
    monkeypatch.setattr(agent_router, "StockScanner", lambda: FakeScanner())
    client = TestClient(app)

    resp = client.post("/agent/scan", json={"symbols": ["600036"], "mode": "position"})

    assert resp.status_code == 400
