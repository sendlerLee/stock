"""数据获取基类，定义统一接口"""
from abc import ABC, abstractmethod
from datetime import date
from typing import Optional
import pandas as pd

from config import Freq


class BaseFetcher(ABC):
    """
    子类需实现：
      - get_kline()    历史 K 线
      - get_realtime() 实时快照（价格/涨跌幅等）
    """

    @abstractmethod
    def get_kline(
        self,
        symbol: str,
        start: date,
        end: date,
        freq: Freq = Freq.D1,
    ) -> pd.DataFrame:
        """
        返回 DataFrame，列名统一为：
            date, open, high, low, close, volume, amount
        date 列类型为 datetime64[ns]，其余为 float64
        """
        ...

    @abstractmethod
    def get_realtime(self, symbol: str) -> dict:
        """
        返回实时快照字典，必须包含键：
            symbol, name, price, change, change_pct, volume, time
        """
        ...

    # ── 工具方法 ──────────────────────────────────────────────────────
    @staticmethod
    def _normalize_columns(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
        """重命名列名到统一格式"""
        return df.rename(columns=col_map)

    @staticmethod
    def _to_float(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
