from src.fetcher.akshare_fetcher import AKShareFetcher
from src.fetcher.yfinance_fetcher import YFinanceFetcher
from config import Market


def get_fetcher(market: Market):
    """根据市场返回合适的 fetcher"""
    if market == Market.US:
        return YFinanceFetcher()
    return AKShareFetcher()
