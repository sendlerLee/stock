"""回测股票池定义。"""
from __future__ import annotations

# 默认回测股票池：复用 reports/actionable_stocks_2026-06-18.md 里的 A/HK/US 标的。
# 格式与 StockTarget.parse 一致：MARKET:SYMBOL。
DEFAULT_BACKTEST_UNIVERSE: list[str] = [
    "A:002475",
    "A:601138",
    "A:688981",
    "A:600036",
    "A:600941",
    "A:300502",
    "A:300308",
    "A:688525",
    "A:300476",
    "A:688347",
    "HK:01024",
    "HK:00700",
    "HK:09988",
    "HK:00005",
    "HK:00981",
    "HK:01347",
    "HK:01810",
    "US:TSM",
    "US:AMD",
    "US:NVDA",
    "US:GOOGL",
    "US:LLY",
    "US:ARM",
    "US:HOOD",
    "US:CRWV",
    "US:IONQ",
]
