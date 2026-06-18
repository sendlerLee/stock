"""全局配置"""
from pathlib import Path
from enum import Enum

# ── 禁用系统代理（macOS 系统代理可能干扰 requests，需在所有 import 前 patch）──
import requests as _req
_orig = _req.Session.merge_environment_settings
def _direct(self, url, proxies, stream, verify, cert):
    s = _orig(self, url, proxies, stream, verify, cert)
    s["proxies"] = {}   # 强制直连
    return s
_req.Session.merge_environment_settings = _direct
# ──────────────────────────────────────────────────────────────────────

# ── 路径 ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "stock.db"

# ── 市场枚举 ─────────────────────────────────────────────────────────
class Market(str, Enum):
    A  = "A"   # A股（沪深）
    HK = "HK"  # 港股
    US = "US"  # 美股

# ── K线频率 ──────────────────────────────────────────────────────────
class Freq(str, Enum):
    D1  = "daily"    # 日线
    W1  = "weekly"   # 周线
    M1  = "monthly"  # 月线

# ── 数据源配置 ────────────────────────────────────────────────────────
# tushare token（可选，留空则使用 akshare 免登录接口）
TUSHARE_TOKEN: str = ""

# ── API 服务配置 ──────────────────────────────────────────────────────
API_HOST = "0.0.0.0"
API_PORT = 8000

# ── 监控默认配置 ──────────────────────────────────────────────────────
# 实时行情刷新间隔（秒），交易时段内
REALTIME_INTERVAL_SECONDS = 60
