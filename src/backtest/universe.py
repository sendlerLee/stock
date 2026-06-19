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

# 股票名称映射：避免依赖实时接口取 name（缓存失败时名称会缺失）。
# 键格式 "MARKET:SYMBOL"，与 DEFAULT_BACKTEST_UNIVERSE 对齐。
STOCK_NAMES: dict[str, str] = {
    "A:002475": "立讯精密",
    "A:601138": "工业富联",
    "A:688981": "中芯国际",
    "A:600036": "招商银行",
    "A:600941": "中国移动",
    "A:300502": "新易盛",
    "A:300308": "中际旭创",
    "A:688525": "佰维存储",
    "A:300476": "胜宏科技",
    "A:688347": "华虹宏力",
    "HK:01024": "快手",
    "HK:00700": "腾讯控股",
    "HK:09988": "阿里巴巴",
    "HK:00005": "汇丰控股",
    "HK:00981": "中芯国际",
    "HK:01347": "华虹宏力",
    "HK:01810": "小米集团",
    "US:TSM": "台积电",
    "US:AMD": "AMD",
    "US:NVDA": "英伟达",
    "US:GOOGL": "谷歌",
    "US:LLY": "礼来",
    "US:ARM": "ARM",
    "US:HOOD": "Robinhood",
    "US:CRWV": "CoreWeave",
    "US:IONQ": "IonQ",
}

