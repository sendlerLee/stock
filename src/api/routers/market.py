"""行情接口：K线、实时快照"""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from config import Market, Freq
from src.fetcher import get_fetcher
from src.indicators import add_all_indicators
from src.storage.db import upsert_kline, query_kline, query_realtime, upsert_realtime

router = APIRouter(prefix="/market", tags=["行情"])


@router.get("/kline")
def get_kline(
    symbol: str = Query(..., description="股票代码，如 000001 / AAPL"),
    market: Market = Query(Market.A, description="市场：A/HK/US"),
    freq: Freq = Query(Freq.D1, description="频率：daily/weekly/monthly"),
    start: date = Query(default=None),
    end: date = Query(default=None),
    indicators: bool = Query(False, description="是否附带技术指标"),
    use_cache: bool = Query(True, description="优先读取本地缓存"),
):
    """获取历史 K 线，可选追加技术指标"""
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=365)

    # 尝试读本地缓存
    if use_cache:
        df = query_kline(symbol, market.value, freq.value, str(start), str(end))
        if df.empty:
            use_cache = False  # 缓存无数据，降级远程拉取

    if not use_cache:
        try:
            fetcher = get_fetcher(market)
            df = fetcher.get_kline(symbol, start, end, freq)
            upsert_kline(df, symbol, market.value, freq.value)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"数据获取失败: {e}")

    if df.empty:
        raise HTTPException(status_code=404, detail="未找到数据")

    if indicators:
        df = add_all_indicators(df)

    # 序列化（date 转字符串，NaN → None）
    import math
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    records = df.to_dict(orient="records")
    # float nan 不是 JSON compliant，逐字段替换为 None
    clean = [
        {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row.items()}
        for row in records
    ]
    return clean


@router.get("/realtime")
def get_realtime(
    symbol: str = Query(..., description="股票代码"),
    market: Market = Query(Market.A, description="市场：A/HK/US"),
    force_refresh: bool = Query(False, description="强制拉取最新行情"),
):
    """获取实时行情快照"""
    if not force_refresh:
        cached = query_realtime(symbol)
        if cached:
            return cached

    try:
        fetcher = get_fetcher(market)
        snap = fetcher.get_realtime(symbol)
        snap["market"] = market.value
        upsert_realtime(snap)
        return snap
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"实时行情获取失败: {e}")
