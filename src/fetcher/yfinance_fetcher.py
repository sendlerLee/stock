"""
美股数据获取，基于 yfinance
symbol 格式：AAPL / MSFT / TSLA，港股可用 0700.HK（yfinance 也支持）
"""
from datetime import date

import yfinance as yf
import pandas as pd

from config import Freq
from src.fetcher.base import BaseFetcher


_FREQ_MAP = {
    Freq.D1: "1d",
    Freq.W1: "1wk",
    Freq.M1: "1mo",
}

_FLOAT_COLS = ["open", "high", "low", "close", "volume"]


class YFinanceFetcher(BaseFetcher):
    """美股（NYSE/NASDAQ）数据获取"""

    def get_kline(
        self,
        symbol: str,
        start: date,
        end: date,
        freq: Freq = Freq.D1,
        auto_adjust: bool = True,  # 自动复权
    ) -> pd.DataFrame:
        interval = _FREQ_MAP.get(freq, "1d")
        ticker = yf.Ticker(symbol)
        df = ticker.history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval=interval,
            auto_adjust=auto_adjust,
        )
        if df.empty:
            raise ValueError(f"yfinance 未返回数据: {symbol}")

        df = df.reset_index()
        # 列名标准化
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        rename = {"date": "date", "datetime": "date"}
        df = df.rename(columns=rename)

        # 确保 date 列存在且为 datetime64
        if "date" not in df.columns:
            df = df.rename(columns={df.columns[0]: "date"})
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

        # 统一成交额（yfinance 无直接 amount，用 close*volume 近似）
        if "volume" in df.columns and "close" in df.columns:
            df["amount"] = df["close"] * df["volume"]

        keep = ["date"] + [c for c in _FLOAT_COLS + ["amount"] if c in df.columns]
        df = df[keep].copy()
        df = self._to_float(df, _FLOAT_COLS + ["amount"])
        df = df.sort_values("date").reset_index(drop=True)
        return df

    def get_realtime(self, symbol: str) -> dict:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = getattr(info, "last_price", None) or 0.0
        prev_close = getattr(info, "previous_close", None) or price
        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0.0

        return {
            "symbol": symbol,
            "name": ticker.info.get("shortName", symbol),
            "price": float(price),
            "change": float(change),
            "change_pct": float(change_pct),
            "volume": float(getattr(info, "three_month_average_volume", 0) or 0),
            "time": "",
        }
