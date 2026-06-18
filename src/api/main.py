"""FastAPI 应用入口"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.api.routers import agent, market, analysis, backtest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(
    title="股票分析系统",
    description="A股/港股/美股 技术分析 · 基本面分析 · 量化回测 · 实时监控",
    version="1.0.0",
)

# CORS（方便前端本地调试）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(market.router)
app.include_router(analysis.router)
app.include_router(backtest.router)
app.include_router(agent.router)

# 静态文件服务
_static_dir = Path(__file__).parent.parent.parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(str(_static_dir / "index.html"))


@app.get("/health", tags=["系统"])
def health():
    return {"status": "ok"}
