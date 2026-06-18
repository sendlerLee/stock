"""
A股（沪深）和港股数据获取，基于 akshare
A股 symbol 格式：000001（纯6位）或 000001.SZ / 600519.SH
港股 symbol 格式：00700（腾讯），内部转为5位补零
"""
import re
from datetime import date
from typing import Optional

# ── 用 curl_cffi 替换 akshare 内部的 requests（解决 TLS 指纹问题）──────
# akshare 部分函数仍用标准 requests，而东财等服务器拒绝其 TLS 握手
# curl_cffi 模拟浏览器指纹，curl_cffi.requests 与 requests 接口兼容
try:
    import curl_cffi.requests as _cffi_req
    import akshare.stock_feature.stock_hist_em as _em
    import types as _types

    # 构造一个代理命名空间：把 requests.get 包装为自动加 impersonate
    class _CffiProxy(_types.ModuleType):
        def get(self, url, **kwargs):
            kwargs.setdefault("impersonate", "chrome")
            return _cffi_req.get(url, **kwargs)
        def __getattr__(self, name):
            return getattr(_cffi_req, name)

    _em.requests = _CffiProxy("curl_cffi_proxy")
except Exception as _e:
    import warnings
    warnings.warn(f"curl_cffi patch 失败，退回标准 requests: {_e}")
# ──────────────────────────────────────────────────────────────────────

import akshare as ak
import pandas as pd

from config import Freq, Market
from src.fetcher.base import BaseFetcher


# akshare period 映射
_FREQ_MAP = {
    Freq.D1: "daily",
    Freq.W1: "weekly",
    Freq.M1: "monthly",
}

# A股历史列名 → 统一格式
_A_COL_MAP = {
    "日期": "date",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
    "成交额": "amount",
}

# 港股历史列名 → 统一格式
_HK_COL_MAP = {
    "日期": "date",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
    "成交额": "amount",
}

_FLOAT_COLS = ["open", "high", "low", "close", "volume", "amount"]


def _strip_suffix(symbol: str) -> str:
    """去掉 .SH / .SZ 后缀，返回纯6位代码"""
    return re.sub(r"\.(SH|SZ|HK)$", "", symbol, flags=re.IGNORECASE)


def _detect_market(symbol: str) -> Market:
    """根据代码前缀判断市场（简单规则）"""
    code = _strip_suffix(symbol)
    if code.startswith(("6", "5")):
        return Market.A   # 上交所
    if code.startswith(("0", "3", "1")):
        return Market.A   # 深交所
    # 港股通常5位，数字开头不符合A股规则时归为港股
    return Market.HK


class AKShareFetcher(BaseFetcher):
    """A股 + 港股数据获取"""

    def get_kline(
        self,
        symbol: str,
        start: date,
        end: date,
        freq: Freq = Freq.D1,
        market: Optional[Market] = None,
        adjust: str = "qfq",  # 前复权
    ) -> pd.DataFrame:
        """
        Parameters
        ----------
        symbol : str  纯代码，如 "000001" 或 "00700"
        adjust : str  复权方式：qfq=前复权, hfq=后复权, "" 不复权
        """
        code = _strip_suffix(symbol)
        mkt = market or _detect_market(code)
        period = _FREQ_MAP.get(freq, "daily")
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        if mkt == Market.A:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period=period,
                start_date=start_str,
                end_date=end_str,
                adjust=adjust,
            )
            df = df.rename(columns=_A_COL_MAP)
        else:
            # 港股：优先 akshare，失败则 fallback 到 yfinance（0700.HK 格式）
            hk_code = code.zfill(5)
            try:
                df = ak.stock_hk_hist(
                    symbol=hk_code,
                    period=period,
                    start_date=start_str,
                    end_date=end_str,
                    adjust=adjust,
                )
                df = df.rename(columns=_HK_COL_MAP)
            except Exception:
                from src.fetcher.yfinance_fetcher import YFinanceFetcher
                yf_symbol = f"{int(code)}.HK"
                df = YFinanceFetcher().get_kline(yf_symbol, start, end, freq)
                # yfinance 已返回标准列名，直接用
                return df

        # 只保留统一列
        keep = ["date"] + [c for c in _FLOAT_COLS if c in df.columns]
        df = df[keep].copy()
        df["date"] = pd.to_datetime(df["date"])
        df = self._to_float(df, _FLOAT_COLS)
        df = df.sort_values("date").reset_index(drop=True)
        return df

    def get_realtime(self, symbol: str) -> dict:
        """实时行情（A股）"""
        code = _strip_suffix(symbol)
        mkt = _detect_market(code)

        if mkt == Market.A:
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == code]
            if row.empty:
                raise ValueError(f"实时行情未找到代码: {code}")
            r = row.iloc[0]
            return {
                "symbol": code,
                "name": r.get("名称", ""),
                "price": float(r.get("最新价", 0)),
                "change": float(r.get("涨跌额", 0)),
                "change_pct": float(r.get("涨跌幅", 0)),
                "volume": float(r.get("成交量", 0)),
                "time": str(r.get("时间", "")),
            }
        else:
            # 港股实时（简化）
            hk_code = code.zfill(5)
            df = ak.stock_hk_spot_em()
            row = df[df["代码"] == hk_code]
            if row.empty:
                raise ValueError(f"港股实时行情未找到代码: {hk_code}")
            r = row.iloc[0]
            return {
                "symbol": hk_code,
                "name": r.get("名称", ""),
                "price": float(r.get("最新价", 0)),
                "change": float(r.get("涨跌额", 0)),
                "change_pct": float(r.get("涨跌幅", 0)),
                "volume": float(r.get("成交量", 0)),
                "time": "",
            }
