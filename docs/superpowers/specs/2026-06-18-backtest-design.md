# 回测系统设计（第一版）

- 日期：2026-06-18
- 请求：`stock-agent-full`
- 状态：已通过头脑风暴确认，待实现
- 目的：验证当前 `StockAgent` 选股逻辑的历史胜率（目的 = 验证，非调优、非策略对比）

---

## 1. 目标与非目标

### 目标

- 用**现在真实在跑的 `StockAgent.evaluate`** 在历史每个交易日逐日生成信号，统计信号触发后多档窗口的收益，回答"这套打分规则到底准不准"。
- 信号判定必须复用 `StockAgent`，零逻辑漂移——回测的就是生产代码。

### 非目标（第一版不做）

- 参数自动调优（阈值/权重搜索）——留作后续增量。
- 多策略权重方案对比——留作后续增量。
- 带止损的主动退出——属于执行层，第一版用纯持有到期，避免污染对信号本身的判断。
- 全市场扫描——第一版用固定小池子。

---

## 2. 方案选择

**方案 A：事件驱动，逐日复用 `StockAgent`（选定）**

每个交易日对池内每只股票用"截止当日"数据构建 snapshot，调 `StockAgent.evaluate`，记录信号；触发后次日开盘建仓，到 N 天评估。

理由：忠实于生产代码，直接复用 `AsOfStockDataProvider`（项目已有，专为 as-of 设计）。池子 ~25 只 × 2 年，性能可接受。

被否方案：
- 方案 B（向量化）：要把打分规则重写一遍，与 `StockAgent` 脱钩，等于验证了另一套逻辑。违背目的。
- 方案 C（数据向量化 + 判定复用）：快+忠实，但复杂度中等，第一版用不上，留作后续优化。

---

## 3. 模块结构

```
src/backtest/
  __init__.py
  universe.py     # 股票池定义
  engine.py       # 逐日事件循环（核心）
  results.py      # 持仓收益聚合 + 指标计算
  report.py       # Markdown 报告生成
scripts/run_backtest.py
tests/test_backtest_engine.py
```

依赖关系（全部复用现有组件）：
- `src.agent.stock_agent.StockAgent` —— 信号判定
- `src.agent.snapshot.SnapshotBuilder` —— snapshot 构建
- `src.agent.providers.AsOfStockDataProvider` —— as-of 数据裁剪
- `src.storage.db` —— K 线本地缓存

---

## 4. 组件设计

### 4.1 `universe.py` —— 股票池

```python
DEFAULT_BACKTEST_UNIVERSE: list[str]  # 如 ["A:600036", "HK:00700", "US:TSM", ...]
```

来源：复用 `reports/actionable_stocks_2026-06-18.md` 里的 ~25 只 A/HK/US 标的。通过 `StockTarget.parse` 解析。

### 4.2 `engine.py` —— 核心事件循环

职责：在回测区间内逐日逐股调用 `StockAgent`，产出原始信号序列。

**输入：**
- `targets: list[StockTarget]`
- `start: date`, `end: date`
- `mode: AgentMode`（trading / position）
- `provider: StockDataProvider`（默认 `DefaultStockDataProvider`）

**流程：**
```
1. 预取全池 K 线 → 存 data/stock.db（kline 表，已存在），后续从本地读
2. 取回测区间内的所有交易日（并集）
3. 对每个交易日 t：
     对每只股票 target：
       provider_t = AsOfStockDataProvider(provider, as_of=t)
       snapshot = SnapshotBuilder(provider_t).build(target)
       decision = StockAgent().evaluate(snapshot, mode)
       记录 SignalRecord(t, symbol, action_state, verdict, buy_score, name)
```

**SignalRecord（dataclass）：**
- `date: date` —— 信号日
- `symbol: str`, `name: str`
- `mode: AgentMode`
- `action_state: ActionState`, `verdict: AgentVerdict`
- `buy_score: float`, `sell_score: float`

**边界：**
- 某 t 某 symbol 的 snapshot 构建失败（数据缺失/网络）→ 记入 `errors`，跳过，不中断。
- as_of 裁剪后 K 线不足以算指标（< 60 根）→ snapshot 的 notes 会记录，decision 仍产出但 confidence 降级。

### 4.3 `results.py` —— 收益聚合与指标

职责：把原始信号序列 + 冷却去重规则 → 持仓交易列表 → 分组指标。

**建仓与冷却规则（已确认）：**
- 触发建仓的 `action_state`：`BUY_NOW`、`PROBE`。
- **冷却：每只股票建仓后，在最长窗口（60 个交易日）内不重复建仓**；冷却期满后，下一个满足条件的信号才算下一单。冷却期内出现的信号被忽略（不延迟、不排队）。
- 同一信号日内同一股票只取最新一次判定（逐日调用天然唯一）。

**持仓收益计算（纯持有到期，已确认）：**
- `entry_date` = 信号日**次日开盘**所在的交易日。
- `entry_price` = 次日开盘价。
- 四档窗口 `N ∈ {5, 10, 20, 60}`：
  - `exit_date` = entry_date 之后第 N 个交易日。
  - `return_n` = (exit_close / entry_open - 1)。
  - 若 exit_date 超出已有数据末尾 → 该档标记为 `insufficient_data`，不参与统计。

**TradeRecord（dataclass）：**
- `signal_date: date`, `symbol: str`, `name: str`
- `action_state: ActionState`, `buy_score: float`
- `entry_date: date`, `entry_price: float`
- `return_5: float|None`, `return_10: float|None`, `return_20: float|None`, `return_60: float|None`

**分组与指标：**
- 按 `action_state` 分组（buy_now / probe）。
- 每组每档窗口算：`win_rate`（收益>0 占比）、`mean_return`、`median_return`、`p25/p75`、`count`。
- `avoid` / `reduce_protect` 作反向对照：看这些标的后续是否确实跑输。
- **基准对照**：等权持有全池同期收益（每个 entry_date，全池平均 N 日收益）——回答"信号是否跑赢盲选"。

### 4.4 `report.py` —— 报告

产出 Markdown，写到 `reports/backtest_result_<start>_<end>.md`，结构：
1. 元信息：区间、池子规模、模式、总信号数、总交易数。
2. 主表：每个 `action_state` × 每档窗口的胜率/均值/中位/样本量。
3. 基准对照：信号组 vs 等权全池。
4. 明细样本：按收益排序的前 5 / 后 5 笔交易（symbol、日期、收益）。
5. **已知偏差声明**（见第 6 节）。

### 4.5 `scripts/run_backtest.py` —— CLI

```
python scripts/run_backtest.py \
  --start 2024-06-01 --end 2026-06-01 \
  --mode trading \
  --output-dir reports
```
参数：`--start`、`--end`、`--mode`、`--days`（snapshot 回看天数，默认 180）、`--output-dir`。默认池子用 `DEFAULT_BACKTEST_UNIVERSE`。

---

## 5. 数据与缓存策略

- K 线预取：engine 启动时对全池调一次拉取，写 `data/stock.db` 的 `kline` 表（已存在，幂等 upsert）。回测循环内 `AsOfStockDataProvider` 从缓存读。
- 交易日历：取全池 K 线日期的并集作为交易日集合。
- 次日开盘价 / N 日后收盘价：从同一份 K 线缓存按 symbol 索引读取。

---

## 6. 已知偏差（报告里必须标注）

第一版坦诚标注，不掩盖：

- ✅ **无未来函数**：趋势/MA/RSI/量比、A 股资金流——这些有历史日期，用 as-of 真实历史值。
- ⚠️ **有未来函数**：PE/PB/ROE/分红/行业题材——免费接口只返回最新值，回测里用的是"今天的值"而非"信号日的值"。
  - 影响范围：trading 模式下 `fundamental` 权重 0.10、`valuation` 权重 0.10，合计 0.20，影响有限但非零。
  - 处理：第一版标注为已知偏差；后续增量可抓历史基本面入库消除。

---

## 7. 测试策略

### 单元测试（`tests/test_backtest_engine.py`）

- 注入 fake provider + 固定构造的 K 线 DataFrame，已知输入 → 已知输出。
- 覆盖：
  - 信号判定正确传递（engine 产出 `action_state` 与手工调 `StockAgent` 一致）。
  - 冷却去重：同一股票连续 60 天 buy_now → 只产出 1 笔交易。
  - 持有期收益计算：entry=次日开盘、N 日后收盘，公式正确。
  - 数据不足档位标记 `insufficient_data`，不进入统计。
  - 指标聚合：胜率/均值/中位计算正确。

### 端到端 smoke

- 小池子（3~5 只）真实数据跑通整个 `run_backtest.py`，确认产出报告。

---

## 8. 成功标准

- `pytest tests/test_backtest_engine.py -q` 全绿。
- 真实小池子 smoke 跑通，产出 `reports/backtest_result_*.md`。
- 报告能清晰回答：`buy_now`/`probe` 信号在 5/10/20/60 天的胜率与是否跑赢等权基准，附样本量。
- 已知偏差在报告中显式标注。

---

## 9. 后续增量（不在本版范围）

1. 消除基本面未来函数：抓历史 PE/PB/ROE 入库，as-of 读取。
2. 参数调优：阈值/权重网格搜索。
3. 带止损退出：叠加 MA20/-7% 止损，看执行层影响。
4. 性能优化：升级到方案 C（数据向量化 + 判定复用）。
