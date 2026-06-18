from src.indicators.trend import add_trend_indicators
from src.indicators.momentum import add_momentum_indicators
from src.indicators.volume import add_volume_indicators


def add_all_indicators(df):
    """一次性添加全部技术指标"""
    df = add_trend_indicators(df)
    df = add_momentum_indicators(df)
    df = add_volume_indicators(df)
    return df
