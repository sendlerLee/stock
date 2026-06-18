"""
实时行情监控与预警
支持：价格阈值预警、指标超买超卖预警
调度器：APScheduler，在交易时段内按 REALTIME_INTERVAL_SECONDS 刷新
"""
import logging
from datetime import datetime
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from config import Market, REALTIME_INTERVAL_SECONDS
from src.fetcher import get_fetcher
from src.storage.db import upsert_realtime

logger = logging.getLogger(__name__)


# ── 预警规则 ──────────────────────────────────────────────────────────
class AlertRule:
    """单个预警规则"""
    def __init__(
        self,
        symbol: str,
        market: Market,
        name: str,
        condition: Callable[[dict], bool],
        message_fn: Callable[[dict], str],
    ):
        self.symbol = symbol
        self.market = market
        self.name = name
        self.condition = condition
        self.message_fn = message_fn
        self.triggered = False  # 防止重复触发

    def check(self, snapshot: dict) -> Optional[str]:
        if self.condition(snapshot):
            if not self.triggered:
                self.triggered = True
                return self.message_fn(snapshot)
        else:
            self.triggered = False  # 条件不满足时重置
        return None


def price_above(threshold: float) -> Callable[[dict], bool]:
    return lambda snap: snap["price"] >= threshold

def price_below(threshold: float) -> Callable[[dict], bool]:
    return lambda snap: snap["price"] <= threshold

def change_pct_above(pct: float) -> Callable[[dict], bool]:
    return lambda snap: snap["change_pct"] >= pct

def change_pct_below(pct: float) -> Callable[[dict], bool]:
    return lambda snap: snap["change_pct"] <= pct


# ── 监控器 ────────────────────────────────────────────────────────────
class StockMonitor:
    def __init__(self):
        self._rules: list[AlertRule] = []
        self._scheduler = BackgroundScheduler()
        self._callbacks: list[Callable[[str, dict], None]] = []

    def add_rule(self, rule: AlertRule) -> "StockMonitor":
        self._rules.append(rule)
        return self

    def add_alert_callback(self, fn: Callable[[str, dict], None]) -> "StockMonitor":
        """注册预警回调，fn(message, snapshot)"""
        self._callbacks.append(fn)
        return self

    def _fetch_and_check(self):
        """定时任务：拉取所有被监控股票实时行情，检查预警规则"""
        symbols = {(r.symbol, r.market) for r in self._rules}
        for symbol, market in symbols:
            try:
                fetcher = get_fetcher(market)
                snap = fetcher.get_realtime(symbol)
                snap["market"] = market.value
                upsert_realtime(snap)
            except Exception as e:
                logger.warning(f"实时行情获取失败 {symbol}: {e}")
                continue

            for rule in self._rules:
                if rule.symbol != symbol:
                    continue
                msg = rule.check(snap)
                if msg:
                    logger.info(f"[预警] {msg}")
                    for cb in self._callbacks:
                        try:
                            cb(msg, snap)
                        except Exception as ce:
                            logger.error(f"预警回调错误: {ce}")

    def start(self):
        """启动后台调度"""
        self._scheduler.add_job(
            self._fetch_and_check,
            trigger="interval",
            seconds=REALTIME_INTERVAL_SECONDS,
            id="realtime_monitor",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info(f"监控已启动，刷新间隔 {REALTIME_INTERVAL_SECONDS}s")

    def stop(self):
        self._scheduler.shutdown(wait=False)
        logger.info("监控已停止")


# ── 终端打印回调（默认） ───────────────────────────────────────────────
def console_alert(message: str, snapshot: dict):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n🔔 [{ts}] {message}")
    print(f"   {snapshot.get('symbol')} {snapshot.get('name')} "
          f"当前价: {snapshot.get('price')}  "
          f"涨跌幅: {snapshot.get('change_pct')}%\n")
