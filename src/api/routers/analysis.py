"""技术分析 + 基本面分析接口"""
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query

from config import Market, Freq
from src.fetcher import get_fetcher
from src.indicators import add_all_indicators
from src.indicators.trend import add_trend_indicators
from src.indicators.momentum import add_momentum_indicators
from src.indicators.volume import add_volume_indicators
from src.strategy.signals import ma_crossover, macd_crossover, rsi_threshold, composite_signal
from src.fundamental.valuation import get_valuation, get_roe_history

router = APIRouter(prefix="/analysis", tags=["分析"])


def _load_df(symbol, market, start, end, freq):
    fetcher = get_fetcher(market)
    df = fetcher.get_kline(symbol, start, end, freq)
    if df.empty:
        raise HTTPException(status_code=404, detail="K线数据为空")
    return df


@router.get("/technical")
def technical_analysis(
    symbol: str = Query(...),
    market: Market = Query(Market.A),
    freq: Freq = Query(Freq.D1),
    days: int = Query(250, description="近N日"),
):
    """计算全套技术指标，返回最新一行汇总"""
    end = date.today()
    start = end - timedelta(days=days + 100)  # 多取一些历史给指标预热
    try:
        df = _load_df(symbol, market, start, end, freq)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    df = add_all_indicators(df)
    last = df.dropna(subset=["ma20", "rsi14"]).iloc[-1]
    result = {k: (None if (v != v) else v) for k, v in last.items()}
    result["date"] = str(result.get("date", ""))
    return result


@router.get("/signals")
def get_signals(
    symbol: str = Query(...),
    market: Market = Query(Market.A),
    freq: Freq = Query(Freq.D1),
    days: int = Query(250),
    strategy: str = Query("ma", description="ma / macd / rsi / composite"),
):
    """生成交易信号序列"""
    end = date.today()
    start = end - timedelta(days=days + 100)
    try:
        df = _load_df(symbol, market, start, end, freq)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    df = add_all_indicators(df)

    strategy_map = {
        "ma":        lambda d: ma_crossover(d),
        "macd":      lambda d: macd_crossover(d),
        "rsi":       lambda d: rsi_threshold(d),
        "composite": lambda d: composite_signal(d),
    }
    if strategy not in strategy_map:
        raise HTTPException(status_code=400, detail=f"不支持的策略: {strategy}")

    sig = strategy_map[strategy](df)
    df["signal"] = sig.values

    # 只返回有信号的行
    sig_df = df[df["signal"] != 0][["date", "close", "signal"]].copy()
    sig_df["date"] = sig_df["date"].dt.strftime("%Y-%m-%d")
    return sig_df.to_dict(orient="records")


@router.get("/fundamental")
def fundamental(
    symbol: str = Query(..., description="A股代码"),
):
    """获取基本面估值指标（仅A股）"""
    try:
        val = get_valuation(symbol)
        roe = get_roe_history(symbol)
        roe_list = roe.to_dict(orient="records") if not roe.empty else []
        return {"valuation": val, "roe_history": roe_list}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
