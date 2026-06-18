# 股票分析系统

A股（沪深）/ 港股 / 美股 一体化分析平台，涵盖：
- **技术分析**：MA、MACD、布林带、RSI、KDJ、OBV 等
- **基本面分析**：PE/PB/ROE、财务报表（A股）
- **量化策略与回测**：5种内置策略，backtrader 引擎，输出夏普/最大回撤/胜率
- **实时行情监控**：价格/涨跌幅预警，后台定时刷新

---

## 快速开始

### 1. 安装依赖

```bash
cd stock
pip install -r requirements.txt
```

### 2. 启动 API 服务

```bash
cd stock
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

访问 `http://localhost:8000` 查看前端界面，`http://localhost:8000/docs` 查看 Swagger 文档。

### 3. 运行测试

```bash
cd stock
pytest tests/test_indicators.py tests/test_signals.py -v
```

---

## 项目结构

```
stock/
├── config.py               全局配置（路径、市场枚举、API key）
├── src/
│   ├── fetcher/            数据获取层
│   │   ├── base.py         BaseFetcher 抽象类
│   │   ├── akshare_fetcher.py   A股/港股（akshare）
│   │   └── yfinance_fetcher.py  美股（yfinance）
│   ├── indicators/         技术指标
│   │   ├── trend.py        MA, MACD, 布林带
│   │   ├── momentum.py     RSI, KDJ, BIAS
│   │   └── volume.py       OBV, VWAP, 量能均线
│   ├── fundamental/        基本面分析
│   │   └── valuation.py    PE/PB/ROE
│   ├── strategy/           量化策略
│   │   ├── signals.py      信号生成（金叉/MACD/RSI/布林/复合）
│   │   └── backtest.py     backtrader 回测封装
│   ├── monitor/            实时监控
│   │   └── alert.py        预警规则 + APScheduler 调度
│   ├── storage/            数据持久化
│   │   └── db.py           SQLite CRUD（kline / realtime_cache）
│   └── api/                FastAPI 后端
│       ├── main.py         应用入口
│       └── routers/
│           ├── market.py   行情接口（K线/实时）
│           ├── analysis.py 技术/信号/基本面接口
│           └── backtest.py 回测接口
├── static/                 前端（ECharts K线图）
├── data/                   SQLite 数据库文件
├── tests/                  单元测试
└── requirements.txt
```

---

## API 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/market/kline` | 历史K线，可选附带指标 |
| GET | `/market/realtime` | 实时行情快照 |
| GET | `/analysis/technical` | 最新指标汇总 |
| GET | `/analysis/signals` | 交易信号序列 |
| GET | `/analysis/fundamental` | 基本面估值（A股） |
| POST | `/backtest/run` | 运行回测 |

---

## 支持的策略

| 策略名 | 说明 |
|--------|------|
| `ma`       | MA5/MA20 金叉死叉 |
| `macd`     | MACD 金叉死叉 |
| `rsi`      | RSI 超买超卖 |
| `bollinger`| 布林带突破 |
| `composite`| 多策略加权投票 |

---

## Stock Agent 选股逻辑

第一版 agent 是研究/决策辅助层，不自动下单。它把统一后的行情、技术指标、基本面、资金流和板块数据打成可解释分数，再输出：

- `buy_candidate`：买入候选，仍需仓位和组合风险确认
- `watch`：观察，等待价格/资金/估值确认
- `hold`：已有仓位可继续持有
- `reduce`：减仓或保护已有仓位
- `avoid`：当前证据下回避新买入

两种模式分开评分：

| 模式 | 适用场景 | 更重视 |
|------|----------|--------|
| `position` | 中线配置、红利、价值修复 | 基本面、估值、分红、盈利稳定性 |
| `trading` | 短线/波段、题材、趋势突破 | 趋势、资金流、板块强度、催化 |

买入分由六类因子组成：趋势、资金流、基本面、估值、板块强度、催化事件。卖出分单独计算，重点看趋势破坏、资金持续流出、基本面恶化和风险惩罚。高估值强趋势票不会被当作价值买入，只会进入交易观察或高风险候选。

示例：

```bash
python3 scripts/stock_agent_demo.py
pytest tests/test_stock_agent.py -q
```

真实数据扫描：

```bash
# 推荐使用项目依赖环境
/Users/didi/conda/bin/python scripts/run_stock_agent.py --sample --mode trading
/Users/didi/conda/bin/python scripts/run_stock_agent.py --symbols A:600036,A:688347,HK:01347 --mode position
/Users/didi/conda/bin/python scripts/run_stock_agent.py --symbols US:AAPL,HK:01347 --mode trading --json
```

API：

```http
POST /agent/scan
{
  "symbols": ["A:600036", "HK:01347", "US:AAPL"],
  "mode": "trading",
  "days": 180
}
```

默认真实数据源：

- A股实时估值：腾讯财经
- A股资金流/板块：东方财富 push2 / push2his
- A股分红与利润增长：东方财富 datacenter + 新浪财报
- 港股实时：腾讯财经
- 港股 K 线：Yahoo chart（使用 `urllib`，避免项目全局 requests 直连 patch 触发 Yahoo 403）
- 美股：项目现有 yfinance fetcher

---

## 实时监控示例（Python）

```python
from config import Market
from src.monitor.alert import StockMonitor, AlertRule, price_below, change_pct_below, console_alert

monitor = StockMonitor()
monitor.add_rule(AlertRule(
    symbol="000001", market=Market.A,
    name="平安银行跌幅预警",
    condition=change_pct_below(-3.0),
    message_fn=lambda s: f"⚠️ {s['name']} 跌幅超过 3%！当前 {s['change_pct']:.2f}%",
))
monitor.add_alert_callback(console_alert)
monitor.start()
```
