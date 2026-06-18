"""
基本面估值分析（A股）
数据来源：akshare
"""
from typing import Optional
import pandas as pd
import akshare as ak


def get_valuation(symbol: str) -> dict:
    """
    获取 A 股实时估值指标（PE/PB/PS/总市值）
    使用 stock_zh_valuation_baidu，分别拉取各指标最新值
    """
    code = symbol.split(".")[0]
    result = {"symbol": code}
    indicators = {
        "pe_ttm":   "市盈率(TTM)",
        "pb":       "市净率",
        "ps_ttm":   "市销率",
        "total_mv": "总市值",
    }
    for key, indicator in indicators.items():
        try:
            df = ak.stock_zh_valuation_baidu(
                symbol=code, indicator=indicator, period="近一年"
            )
            if not df.empty:
                result[key] = _safe_float(df.iloc[-1]["value"])
            else:
                result[key] = None
        except Exception:
            result[key] = None

    # 总市值单位是亿元（百度直接返回亿）
    return result


def get_roe_history(symbol: str) -> pd.DataFrame:
    """
    获取历史 ROE 数据
    返回 DataFrame，列：date, roe
    """
    code = symbol.split(".")[0]
    try:
        df = ak.stock_financial_analysis_indicator(symbol=code)
        if df.empty:
            return pd.DataFrame()
        roe_cols = [c for c in df.columns if "净资产收益率" in c or "ROE" in c.upper()]
        date_cols = [c for c in df.columns if "日期" in c or "报告期" in c]
        if not roe_cols or not date_cols:
            return pd.DataFrame()
        result = df[date_cols[:1] + roe_cols[:1]].copy()
        result.columns = ["date", "roe"]
        result["roe"] = pd.to_numeric(result["roe"], errors="coerce")
        return result.dropna().reset_index(drop=True)
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})


def _safe_float(val) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None
