"""
Build StockSnapshot objects from provider data.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

from src.agent.providers import DefaultStockDataProvider, StockDataProvider, StockTarget
from src.agent.stock_agent import StockSnapshot
from src.indicators import add_all_indicators


@dataclass
class SnapshotBuilder:
    provider: Optional[StockDataProvider] = None

    def __post_init__(self):
        if self.provider is None:
            self.provider = DefaultStockDataProvider()

    def build(self, target: StockTarget, days: int = 180) -> StockSnapshot:
        notes = list(target.notes)
        kline = self._safe_call("kline", notes, lambda: self.provider.get_kline(target, days))
        realtime = self._safe_call("realtime", notes, lambda: self.provider.get_realtime(target)) or {}
        valuation = self._safe_call("valuation", notes, lambda: self.provider.get_valuation(target)) or {}
        flow = self._safe_call("flow", notes, lambda: self.provider.get_flow(target)) or {}
        sector = self._safe_call("sector", notes, lambda: self.provider.get_sector(target)) or {}

        metrics = self._technical_metrics(kline, notes)
        name = target.name or str(realtime.get("name") or valuation.get("name") or target.symbol)
        price = pick_float(realtime, "price") or metrics.get("price")
        amount = pick_float(realtime, "amount", "amount_wan")
        if amount is not None and "amount_wan" in realtime and "amount" not in realtime:
            amount *= 10_000

        return StockSnapshot(
            symbol=target.symbol,
            name=name,
            market=target.market.value,
            price=price,
            change_pct=pick_float(realtime, "change_pct"),
            turnover_pct=pick_float(realtime, "turnover_pct"),
            amount=amount,
            pe_ttm=pick_float(realtime, "pe_ttm", "pe") or pick_float(valuation, "pe_ttm", "pe"),
            pb=pick_float(realtime, "pb") or pick_float(valuation, "pb"),
            dividend_yield=pick_float(valuation, "dividend_yield"),
            roe=pick_float(valuation, "roe"),
            revenue_growth=pick_float(valuation, "revenue_growth"),
            profit_growth=pick_float(valuation, "profit_growth"),
            ma20=metrics.get("ma20"),
            ma60=metrics.get("ma60"),
            rsi14=metrics.get("rsi14"),
            volume_ratio=metrics.get("volume_ratio") or pick_float(realtime, "volume_ratio", "vol_ratio"),
            flow_5d=pick_float(flow, "flow_5d", "main_5d", "main_net_5d"),
            flow_20d=pick_float(flow, "flow_20d", "main_20d", "main_net_20d"),
            flow_60d=pick_float(flow, "flow_60d", "main_60d", "main_net_60d"),
            sector_change_pct=pick_float(sector, "sector_change_pct", "change_pct"),
            catalyst_score=pick_float(sector, "catalyst_score"),
            tags=list(dict.fromkeys(target.tags + list(sector.get("tags", [])))),
            notes=notes + list(sector.get("notes", [])),
            raw={
                "realtime": realtime,
                "valuation": valuation,
                "flow": flow,
                "sector": sector,
                "technical": metrics,
            },
        )

    def _technical_metrics(self, df: Any, notes: list[str]) -> dict[str, float]:
        if not isinstance(df, pd.DataFrame) or df.empty:
            notes.append("kline unavailable; technical factors are incomplete")
            return {}
        try:
            enriched = add_all_indicators(df.copy())
            last = enriched.dropna(subset=["ma20", "ma60", "rsi14"]).iloc[-1]
            volume_ratio = None
            if "volume" in enriched and "vol_ma10" in enriched:
                vol_ma10 = last.get("vol_ma10")
                if vol_ma10:
                    volume_ratio = float(last.get("volume", 0)) / float(vol_ma10)
            return {
                "price": safe_float(last.get("close")),
                "ma20": safe_float(last.get("ma20")),
                "ma60": safe_float(last.get("ma60")),
                "rsi14": safe_float(last.get("rsi14")),
                "volume_ratio": safe_float(volume_ratio),
            }
        except Exception as exc:
            notes.append(f"technical calculation failed: {exc}")
            return {}

    def _safe_call(self, name: str, notes: list[str], fn):
        try:
            return fn()
        except Exception as exc:
            notes.append(f"{name} provider failed: {exc}")
            return None


def pick_float(source: dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        if key in source:
            value = safe_float(source.get(key))
            if value is not None:
                return value
    return None


def safe_float(value: Any) -> Optional[float]:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
