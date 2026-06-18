"""
Data provider interfaces for the stock agent.

Providers keep network and vendor-specific behavior outside the scoring layer.
The default provider uses the existing project fetchers plus lightweight
best-effort extras. Tests can inject fake providers without touching network.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional, Protocol

import pandas as pd
import requests

from config import Freq, Market
from src.fetcher import get_fetcher
from src.fundamental.valuation import get_valuation


UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


@dataclass(frozen=True)
class StockTarget:
    market: Market
    symbol: str
    name: str = ""
    notes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, raw: str) -> "StockTarget":
        """Parse strings like A:600036, HK:01347, US:AAPL."""
        if ":" not in raw:
            raise ValueError(f"target must use MARKET:SYMBOL format: {raw}")
        market_raw, symbol = raw.split(":", 1)
        market = Market(market_raw.upper())
        return cls(market=market, symbol=symbol.strip())


class StockDataProvider(Protocol):
    def get_kline(self, target: StockTarget, days: int = 180) -> pd.DataFrame:
        ...

    def get_realtime(self, target: StockTarget) -> dict[str, Any]:
        ...

    def get_valuation(self, target: StockTarget) -> dict[str, Any]:
        ...

    def get_flow(self, target: StockTarget) -> dict[str, Any]:
        ...

    def get_sector(self, target: StockTarget) -> dict[str, Any]:
        ...


class DefaultStockDataProvider:
    """Best-effort provider backed by existing fetchers and valuation helpers."""

    def get_kline(self, target: StockTarget, days: int = 180) -> pd.DataFrame:
        if target.market == Market.HK:
            yahoo_symbol = f"{int(target.symbol):04d}.HK"
            return yahoo_chart_kline(yahoo_symbol, days)
        if target.market == Market.US:
            return yahoo_chart_kline(target.symbol.upper(), days)
        end = date.today() + timedelta(days=1)
        start = end - timedelta(days=days + 100)
        fetcher = get_fetcher(target.market)
        return fetcher.get_kline(target.symbol, start, end, Freq.D1)

    def get_realtime(self, target: StockTarget) -> dict[str, Any]:
        if target.market == Market.A:
            return a_share_tencent_quote(target.symbol)
        if target.market == Market.HK:
            return hk_tencent_quote(target.symbol.zfill(5))
        if target.market == Market.US:
            return yahoo_realtime_from_chart(target.symbol.upper())
        return get_fetcher(target.market).get_realtime(target.symbol)

    def get_valuation(self, target: StockTarget) -> dict[str, Any]:
        if target.market == Market.A:
            valuation = {}
            try:
                valuation.update(get_valuation(target.symbol))
            except Exception:
                pass
            valuation.update(a_share_dividend_and_growth(target.symbol))
            return valuation
        return {}

    def get_flow(self, target: StockTarget) -> dict[str, Any]:
        if target.market == Market.A:
            return a_share_fund_flow_summary(target.symbol)
        return {}

    def get_sector(self, target: StockTarget) -> dict[str, Any]:
        if target.market == Market.A:
            return a_share_sector(target.symbol)
        return {}


class AsOfStockDataProvider:
    """Provider wrapper for end-of-day/as-of reports.

    K-line data is clipped to ``as_of`` and realtime price/change/amount are
    derived from the last available bar. Fundamentals and sector metadata remain
    best-effort latest data because many public free endpoints do not expose
    historical point-in-time snapshots.
    """

    def __init__(self, base: Optional[StockDataProvider] = None, as_of: Optional[date] = None):
        self.base = base or DefaultStockDataProvider()
        self.as_of = as_of or date.today()
        self._kline_cache: dict[tuple[str, str, int], pd.DataFrame] = {}

    def get_kline(self, target: StockTarget, days: int = 180) -> pd.DataFrame:
        key = (target.market.value, target.symbol, days)
        if key not in self._kline_cache:
            df = self.base.get_kline(target, days + 30)
            if "date" in df.columns:
                dates = pd.to_datetime(df["date"]).dt.date
                df = df[dates <= self.as_of].copy()
            self._kline_cache[key] = df.tail(days).reset_index(drop=True)
        return self._kline_cache[key].copy()

    def get_realtime(self, target: StockTarget) -> dict[str, Any]:
        df = self.get_kline(target, 180)
        if df.empty:
            return self.base.get_realtime(target)
        last = df.iloc[-1]
        prev_close = df.iloc[-2]["close"] if len(df) >= 2 else last["close"]
        change_pct = ((last["close"] / prev_close - 1) * 100) if prev_close else None
        amount = to_float(last.get("amount"))
        return {
            "name": target.name or target.symbol,
            "price": to_float(last.get("close")),
            "change_pct": change_pct,
            "amount": amount,
            "volume": to_float(last.get("volume")),
        }

    def get_valuation(self, target: StockTarget) -> dict[str, Any]:
        return self.base.get_valuation(target)

    def get_flow(self, target: StockTarget) -> dict[str, Any]:
        return self.base.get_flow(target)

    def get_sector(self, target: StockTarget) -> dict[str, Any]:
        return self.base.get_sector(target)


def a_share_tencent_quote(code: str) -> dict[str, Any]:
    prefix = "sh" if code.startswith(("6", "9")) else "sz"
    url = f"https://qt.gtimg.cn/q={prefix}{code}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    data = urllib.request.urlopen(req, timeout=10).read().decode("gbk")
    vals = _quote_fields(data)
    if len(vals) < 53:
        return {}
    return {
        "name": vals[1],
        "price": to_float(vals[3]),
        "change_pct": to_float(vals[32]),
        "amount_wan": to_float(vals[37]),
        "turnover_pct": to_float(vals[38]),
        "pe_ttm": to_float(vals[39]),
        "pb": to_float(vals[46]),
        "vol_ratio": to_float(vals[49]),
        "pe_static": to_float(vals[52]),
    }


def hk_tencent_quote(code: str) -> dict[str, Any]:
    text = requests.get(f"https://qt.gtimg.cn/q=r_hk{code}", headers={"User-Agent": UA}, timeout=10)
    text.encoding = "gbk"
    vals = _quote_fields(text.text)
    if len(vals) < 57:
        return {}
    return {
        "name": vals[1],
        "price": to_float(vals[3]),
        "change_pct": to_float(vals[32]),
        "amount": to_float(vals[37]),
        "pe": to_float(vals[39]),
        "pb": to_float(vals[56]),
    }


def yahoo_chart_kline(symbol: str, days: int = 180) -> pd.DataFrame:
    range_ = "1y" if days > 180 else "6mo"
    params = urllib.parse.urlencode({"interval": "1d", "range": range_})
    d = None
    last_error = None
    for host in ("query2.finance.yahoo.com", "query1.finance.yahoo.com"):
        url = f"https://{host}/v8/finance/chart/{symbol}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                d = json_loads(resp.read().decode("utf-8"))
            break
        except Exception as exc:
            last_error = exc
    if d is None:
        raise RuntimeError(f"Yahoo chart failed for {symbol}: {last_error}")
    chart = d.get("chart", {}).get("result", [{}])[0]
    timestamps = chart.get("timestamp", [])
    quote = chart.get("indicators", {}).get("quote", [{}])[0]
    rows = []
    for i, ts in enumerate(timestamps):
        close = quote.get("close", [None])[i]
        if close is None:
            continue
        volume = quote.get("volume", [0])[i] or 0
        rows.append(
            {
                "date": datetime.fromtimestamp(ts),
                "open": quote.get("open", [None])[i],
                "high": quote.get("high", [None])[i],
                "low": quote.get("low", [None])[i],
                "close": close,
                "volume": volume,
                "amount": close * volume,
            }
        )
    return pd.DataFrame(rows).tail(days).reset_index(drop=True)


def yahoo_realtime_from_chart(symbol: str) -> dict[str, Any]:
    df = yahoo_chart_kline(symbol, 5)
    if df.empty:
        return {"name": symbol}
    last = df.iloc[-1]
    prev_close = df.iloc[-2]["close"] if len(df) >= 2 else last["close"]
    change_pct = ((last["close"] / prev_close - 1) * 100) if prev_close else None
    return {
        "name": symbol,
        "price": to_float(last.get("close")),
        "change_pct": change_pct,
        "amount": to_float(last.get("amount")),
        "volume": to_float(last.get("volume")),
    }


def json_loads(text: str) -> dict[str, Any]:
    import json

    return json.loads(text)


def a_share_fund_flow_summary(code: str) -> dict[str, Any]:
    rows = a_share_fund_flow_rows(code)
    summary = {}
    for window in (5, 20, 60):
        recent = rows[-window:]
        summary[f"flow_{window}d"] = round(sum(item["main_net"] for item in recent) / 1e8, 3) if recent else None
    return summary


def a_share_fund_flow_rows(code: str) -> list[dict[str, Any]]:
    secid = f"1.{code}" if code.startswith("6") else f"0.{code}"
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "lmt": "120",
    }
    d = requests.get(url, params=params, headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}, timeout=15).json()
    rows = []
    for line in d.get("data", {}).get("klines", []):
        parts = line.split(",")
        if len(parts) >= 6:
            rows.append({"date": parts[0], "main_net": to_float(parts[1]) or 0, "super_net": to_float(parts[5]) or 0})
    return rows


def a_share_sector(code: str) -> dict[str, Any]:
    secid = f"1.{code}" if code.startswith("6") else f"0.{code}"
    params = {
        "fltt": "2",
        "invt": "2",
        "secid": secid,
        "spt": "3",
        "pi": "0",
        "pz": "200",
        "po": "1",
        "fields": "f12,f14,f3,f128",
    }
    d = requests.get(
        "https://push2.eastmoney.com/api/qt/slist/get",
        params=params,
        headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"},
        timeout=15,
    ).json()
    diff = (d.get("data") or {}).get("diff") or {}
    items = list(diff.values()) if isinstance(diff, dict) else list(diff)
    tags = [item.get("f14", "") for item in items if item.get("f14")]
    sector_change = None
    if items:
        sector_change = to_float(items[0].get("f3"))
    catalyst = min(100, 15 * sum(1 for word in ("半导体", "存储", "高股息", "银行", "AI") if word in " ".join(tags)))
    return {"sector_change_pct": sector_change, "tags": tags[:20], "catalyst_score": catalyst}


def a_share_dividend_and_growth(code: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    dividend = latest_dividend_per_share(code)
    price = (a_share_tencent_quote(code) or {}).get("price")
    if dividend and price:
        result["dividend_yield"] = round(dividend / price * 100, 3)
    growth = sina_income_growth(code)
    result.update(growth)
    return result


def latest_dividend_per_share(code: str) -> Optional[float]:
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_SHAREBONUS_DET",
        "columns": "ALL",
        "filter": f'(SECURITY_CODE="{code}")',
        "pageNumber": "1",
        "pageSize": "4",
        "sortColumns": "EX_DIVIDEND_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
    }
    try:
        data = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15).json()
        rows = data.get("result", {}).get("data", []) or []
    except Exception:
        return None
    total = 0.0
    for row in rows[:2]:
        value = to_float(row.get("PRETAX_BONUS_RMB"))
        if value:
            total += value / 10.0
    return total or None


def sina_income_growth(code: str) -> dict[str, Any]:
    prefix = "sh" if code.startswith("6") else "sz"
    url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
    params = {
        "paperCode": f"{prefix}{code}",
        "source": "lrb",
        "type": "0",
        "page": "1",
        "num": "1",
    }
    try:
        data = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15).json()
        report_list = data.get("result", {}).get("data", {}).get("report_list", {}) or {}
    except Exception:
        return {}
    if not report_list:
        return {}
    latest_key = sorted(report_list.keys(), reverse=True)[0]
    result = {}
    for item in report_list[latest_key].get("data", []) or []:
        title = item.get("item_title", "")
        yoy = to_float(item.get("item_tongbi"))
        if title == "营业收入" and yoy is not None:
            result["revenue_growth"] = round(yoy * 100, 3)
        elif title == "归属于母公司的净利润" and yoy is not None:
            result["profit_growth"] = round(yoy * 100, 3)
        elif title == "基本每股收益":
            result["eps"] = to_float(item.get("item_value"))
    return result


def _quote_fields(text: str) -> list[str]:
    match = re.search(r'"(.+)"', text)
    return match.group(1).split("~") if match else []


def to_float(value: Any) -> Optional[float]:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
