/* 股票分析系统前端 */
const API = '';  // 同源，前缀为空

let klineChart, signalChart, equityChart;

// ── 工具 ──────────────────────────────────────────────────────────────
function status(msg) {
  document.getElementById('status').textContent = msg;
}

async function fetchJSON(url) {
  const res = await fetch(API + url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function sym()      { return document.getElementById('symbol').value.trim(); }
function market()   { return document.getElementById('market').value; }
function days()     { return document.getElementById('days').value; }
function strategy() { return document.getElementById('strategy').value; }

// ── Tab 切换 ──────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t, i) => {
    const panels = ['kline', 'signals', 'backtest', 'fundamental'];
    t.classList.toggle('active', panels[i] === name);
  });
  document.querySelectorAll('.panel').forEach(p => {
    p.classList.toggle('active', p.id === `panel-${name}`);
  });
  // 切换时 resize 图表防止宽度异常
  if (name === 'kline' && klineChart) klineChart.resize();
  if (name === 'signals' && signalChart) signalChart.resize();
  if (name === 'backtest' && equityChart) equityChart.resize();
}

// ── K 线图 ────────────────────────────────────────────────────────────
async function loadKline() {
  status('加载K线…');
  const end = new Date().toISOString().slice(0, 10);
  const startDate = new Date(Date.now() - days() * 86400e3).toISOString().slice(0, 10);
  const url = `/market/kline?symbol=${sym()}&market=${market()}&start=${startDate}&end=${end}&indicators=true&use_cache=false`;
  const data = await fetchJSON(url);

  const dates  = data.map(d => d.date);
  const ohlc   = data.map(d => [d.open, d.close, d.low, d.high]);
  const vols   = data.map(d => d.volume);
  const ma5    = data.map(d => d.ma5 ?? '-');
  const ma20   = data.map(d => d.ma20 ?? '-');
  const macdH  = data.map(d => d.macd_hist ?? 0);

  if (!klineChart) {
    klineChart = echarts.init(document.getElementById('kline-chart'), 'dark');
    window.addEventListener('resize', () => klineChart.resize());
  }

  klineChart.setOption({
    backgroundColor: '#0d1117',
    legend: { data: ['K线', 'MA5', 'MA20'], top: 4 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: [
      { left: 60, right: 20, top: 40, height: '52%' },
      { left: 60, right: 20, top: '62%', height: '15%' },
      { left: 60, right: 20, top: '80%', height: '15%' },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 2 },
    ],
    yAxis: [
      { scale: true, gridIndex: 0 },
      { gridIndex: 1 },
      { gridIndex: 2 },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, 2], start: 60, end: 100 },
      { xAxisIndex: [0, 1, 2], start: 60, end: 100, bottom: 4 },
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', data: ohlc, xAxisIndex: 0, yAxisIndex: 0,
        itemStyle: { color: '#3fb950', color0: '#f85149', borderColor: '#3fb950', borderColor0: '#f85149' },
      },
      { name: 'MA5', type: 'line', data: ma5, xAxisIndex: 0, yAxisIndex: 0,
        lineStyle: { width: 1 }, symbol: 'none', smooth: false },
      { name: 'MA20', type: 'line', data: ma20, xAxisIndex: 0, yAxisIndex: 0,
        lineStyle: { width: 1 }, symbol: 'none', smooth: false },
      {
        name: '成交量', type: 'bar', data: vols, xAxisIndex: 1, yAxisIndex: 1,
        itemStyle: { color: (p) => data[p.dataIndex].close >= data[p.dataIndex].open ? '#3fb950' : '#f85149' },
      },
      {
        name: 'MACD', type: 'bar', data: macdH, xAxisIndex: 2, yAxisIndex: 2,
        itemStyle: { color: (p) => macdH[p.dataIndex] >= 0 ? '#3fb950' : '#f85149' },
      },
    ],
  });
  status(`K线加载完成，共 ${data.length} 根`);
}

// ── 信号图 ────────────────────────────────────────────────────────────
async function loadSignals() {
  status('加载信号…');
  const url = `/analysis/signals?symbol=${sym()}&market=${market()}&days=${days()}&strategy=${strategy()}`;
  const data = await fetchJSON(url);

  // 更新表格
  const tbody = document.querySelector('#signals-table tbody');
  tbody.innerHTML = data.map(r => `
    <tr>
      <td>${r.date}</td>
      <td>${r.close?.toFixed(2) ?? '-'}</td>
      <td class="${r.signal === 1 ? 'signal-buy' : 'signal-sell'}">${r.signal === 1 ? '▲ 买入' : '▼ 卖出'}</td>
    </tr>`).join('');

  // 同时加载 K 线作为背景
  const endDate = new Date().toISOString().slice(0, 10);
  const startDate = new Date(Date.now() - days() * 86400e3).toISOString().slice(0, 10);
  const kline = await fetchJSON(`/market/kline?symbol=${sym()}&market=${market()}&start=${startDate}&end=${endDate}&use_cache=false`);

  if (!signalChart) {
    signalChart = echarts.init(document.getElementById('signal-chart'), 'dark');
    window.addEventListener('resize', () => signalChart.resize());
  }

  const dates = kline.map(d => d.date);
  const ohlc  = kline.map(d => [d.open, d.close, d.low, d.high]);
  const buyPts  = data.filter(s => s.signal === 1).map(s => ({ coord: [s.date, s.close], symbol: 'triangle', symbolSize: 12, itemStyle: { color: '#3fb950' } }));
  const sellPts = data.filter(s => s.signal === -1).map(s => ({ coord: [s.date, s.close], symbol: 'triangle', symbolRotate: 180, symbolSize: 12, itemStyle: { color: '#f85149' } }));

  signalChart.setOption({
    backgroundColor: '#0d1117',
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: { left: 60, right: 20, top: 20, bottom: 60 },
    xAxis: { type: 'category', data: dates },
    yAxis: { scale: true },
    dataZoom: [{ type: 'inside', start: 60, end: 100 }, { start: 60, end: 100 }],
    series: [
      {
        name: 'K线', type: 'candlestick', data: ohlc,
        itemStyle: { color: '#3fb950', color0: '#f85149', borderColor: '#3fb950', borderColor0: '#f85149' },
        markPoint: { data: [...buyPts, ...sellPts] },
      },
    ],
  });
  status(`信号加载完成，共 ${data.length} 个信号`);
}

// ── 回测 ──────────────────────────────────────────────────────────────
async function runBacktest() {
  status('回测运行中…');
  const endDate = new Date().toISOString().slice(0, 10);
  const startDate = new Date(Date.now() - days() * 86400e3).toISOString().slice(0, 10);

  const body = {
    symbol: sym(), market: market(), strategy: strategy(),
    start: startDate, end: endDate,
  };
  const res = await fetch(`${API}/backtest/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    status(`回测失败: ${err.detail || res.statusText}`);
    return;
  }
  const data = await res.json();

  // 指标卡片
  const metricsEl = document.getElementById('bt-metrics');
  const fmt = (v, suffix = '') => v == null ? 'N/A' : `${v}${suffix}`;
  const colorClass = (v) => v > 0 ? 'pos' : v < 0 ? 'neg' : 'neu';
  metricsEl.innerHTML = [
    ['总收益率', fmt(data.total_return, '%'), colorClass(data.total_return)],
    ['年化收益', fmt(data.annual_return, '%'), colorClass(data.annual_return)],
    ['夏普比率', fmt(data.sharpe_ratio), colorClass(data.sharpe_ratio)],
    ['最大回撤', fmt(data.max_drawdown, '%'), 'neg'],
    ['胜率', fmt(data.win_rate, '%'), 'neu'],
    ['交易次数', fmt(data.trade_count), 'neu'],
    ['最终资产', data.final_value?.toLocaleString() ?? 'N/A', colorClass(data.total_return)],
  ].map(([label, value, cls]) => `
    <div class="metric-card">
      <div class="label">${label}</div>
      <div class="value ${cls}">${value}</div>
    </div>`).join('');

  // 资产曲线
  const equity = data.equity_curve || {};
  const eqDates = Object.keys(equity);
  const eqVals  = Object.values(equity);

  // 先切 Tab，让 div 可见，再初始化图表（否则宽度为0）
  switchTab('backtest');
  if (!equityChart) {
    equityChart = echarts.init(document.getElementById('equity-chart'), 'dark');
    window.addEventListener('resize', () => equityChart.resize());
  }

  equityChart.setOption({
    backgroundColor: '#0d1117',
    tooltip: { trigger: 'axis' },
    grid: { left: 80, right: 20, top: 20, bottom: 60 },
    xAxis: { type: 'category', data: eqDates },
    yAxis: { scale: true, axisLabel: { formatter: v => v.toLocaleString() } },
    dataZoom: [{ type: 'inside' }, {}],
    series: [{
      name: '资产', type: 'line', data: eqVals,
      areaStyle: { opacity: 0.15 }, symbol: 'none',
      lineStyle: { color: '#58a6ff' }, itemStyle: { color: '#58a6ff' },
    }],
  });
  equityChart.resize();
  status('回测完成');
}

// ── 基本面 ────────────────────────────────────────────────────────────
async function loadFundamental() {
  if (market() !== 'A') {
    document.getElementById('fundamental-metrics').innerHTML =
      '<p style="color:#8b949e;padding:16px">基本面数据目前仅支持A股</p>';
    return;
  }
  status('加载基本面…');
  const data = await fetchJSON(`/analysis/fundamental?symbol=${sym()}`);
  const val = data.valuation || {};
  const metricsEl = document.getElementById('fundamental-metrics');
  metricsEl.innerHTML = [
    ['PE(TTM)', val.pe_ttm?.toFixed(2) ?? 'N/A'],
    ['PB', val.pb?.toFixed(2) ?? 'N/A'],
    ['PS(TTM)', val.ps_ttm?.toFixed(2) ?? 'N/A'],
    ['总市值(亿)', val.total_mv ? (val.total_mv / 10000).toFixed(2) : 'N/A'],
  ].map(([label, value]) => `
    <div class="metric-card">
      <div class="label">${label}</div>
      <div class="value neu">${value}</div>
    </div>`).join('');
  status('基本面加载完成');
}

// ── 主入口 ────────────────────────────────────────────────────────────
async function loadAll() {
  try {
    await Promise.all([loadKline(), loadSignals()]);
    loadFundamental();
  } catch (e) {
    status(`错误: ${e.message}`);
    console.error(e);
  }
}

// 页面加载时自动触发
loadAll();
