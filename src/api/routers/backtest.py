"""回测接口"""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import Market, Freq
from src.fetcher import get_fetcher
from src.indicators import add_all_indicators
from src.strategy.signals import (
    ma_crossover, macd_crossover, rsi_threshold,
    composite_signal, bollinger_breakout,
)
from src.strategy.backtest import run_backtest

router = APIRouter(prefix="/backtest", tags=["回测"])


class BacktestRequest(BaseModel):
    symbol: str = Field(..., example="000001")
    market: Market = Market.A
    freq: Freq = Freq.D1
    start: date = Field(default=None)
    end: date = Field(default=None)
    strategy: Literal["ma", "macd", "rsi", "bollinger", "composite"] = "ma"
    initial_cash: float = Field(100_000.0, ge=10_000)
    commission: float = Field(0.001, ge=0, le=0.05)
    stake: int = Field(100, ge=1)


@router.post("/run")
def run(req: BacktestRequest):
    """运行回测，返回绩效指标和资产曲线"""
    end = req.end or date.today()
    start = req.start or (end - timedelta(days=365 * 3))

    try:
        fetcher = get_fetcher(req.market)
        df = fetcher.get_kline(req.symbol, start, end, req.freq)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"K线数据获取失败: {e}")

    if len(df) < 60:
        raise HTTPException(status_code=400, detail="数据量不足，至少需要60根K线")

    df = add_all_indicators(df)

    sig_map = {
        "ma":        lambda d: ma_crossover(d),
        "macd":      lambda d: macd_crossover(d),
        "rsi":       lambda d: rsi_threshold(d),
        "bollinger": lambda d: bollinger_breakout(d),
        "composite": lambda d: composite_signal(d),
    }
    signal = sig_map[req.strategy](df)

    try:
        result = run_backtest(
            df, signal,
            initial_cash=req.initial_cash,
            commission=req.commission,
            stake=req.stake,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回测运行失败: {e}")

    result["symbol"] = req.symbol
    result["strategy"] = req.strategy
    result["period"] = {"start": str(start), "end": str(end)}
    return result
