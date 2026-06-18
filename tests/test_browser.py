"""
浏览器端到端测试（Playwright + 系统 Chrome）
测试内容：
  1. 首页加载，标题正确
  2. K线图 canvas 渲染
  3. 实时行情 API 可达
  4. 回测接口返回正确结构
  5. Swagger 文档页可访问
"""
import pytest
from playwright.sync_api import sync_playwright, Page, expect
import requests

BASE = "http://localhost:8000"


# ── HTTP 接口冒烟测试（无需浏览器）────────────────────────────────────
def test_health():
    r = requests.get(f"{BASE}/health", timeout=5)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_swagger_reachable():
    r = requests.get(f"{BASE}/docs", timeout=5)
    assert r.status_code == 200
    assert "swagger" in r.text.lower()


def test_kline_api():
    r = requests.get(
        f"{BASE}/market/kline",
        params={"symbol": "000001", "market": "A", "start": "2024-01-01", "end": "2024-06-01", "use_cache": "false"},
        timeout=30,
    )
    assert r.status_code == 200, f"kline 失败: {r.text[:200]}"
    data = r.json()
    assert isinstance(data, list) and len(data) > 0
    first = data[0]
    for col in ["date", "open", "high", "low", "close", "volume"]:
        assert col in first, f"缺少列: {col}"


def test_signals_api():
    r = requests.get(
        f"{BASE}/analysis/signals",
        params={"symbol": "000001", "market": "A", "days": "365", "strategy": "ma"},
        timeout=30,
    )
    assert r.status_code == 200, f"signals 失败: {r.text[:200]}"
    data = r.json()
    assert isinstance(data, list)
    if data:
        assert "signal" in data[0]
        assert data[0]["signal"] in (1, -1)


def test_backtest_api():
    payload = {
        "symbol": "000001",
        "market": "A",
        "strategy": "ma",
        "start": "2022-01-01",
        "end": "2024-01-01",
        "initial_cash": 100000,
    }
    r = requests.post(f"{BASE}/backtest/run", json=payload, timeout=60)
    assert r.status_code == 200, f"backtest 失败: {r.text[:200]}"
    result = r.json()
    for key in ["total_return", "sharpe_ratio", "max_drawdown", "win_rate", "equity_curve"]:
        assert key in result, f"回测结果缺少字段: {key}"


# ── 浏览器 UI 测试 ────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",     # 使用系统 Chrome，不下载 Chromium
            headless=True,
        )
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        pg = ctx.new_page()
        yield pg
        browser.close()


def test_homepage_title(page: Page):
    page.goto(BASE, wait_until="networkidle", timeout=15000)
    expect(page).to_have_title("股票分析系统")


def test_header_visible(page: Page):
    expect(page.locator("header h1")).to_contain_text("股票分析系统")


def test_kline_chart_rendered(page: Page):
    # ECharts 会在 canvas 上渲染，等待 canvas 出现
    page.goto(BASE, wait_until="networkidle", timeout=15000)
    # 等待图表区存在
    canvas = page.locator("#kline-chart canvas")
    canvas.wait_for(state="attached", timeout=20000)
    assert canvas.count() > 0, "K线图 canvas 未渲染"


def test_tab_switch(page: Page):
    # 点击"信号"tab
    page.locator(".tab", has_text="信号").click()
    expect(page.locator("#panel-signals")).to_be_visible()


def test_screenshot(page: Page, tmp_path):
    page.goto(BASE, wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(3000)   # 等图表加载
    shot = "/tmp/stock_ui.png"
    page.screenshot(path=shot, full_page=False)
    print(f"\n截图已保存: {shot}")
