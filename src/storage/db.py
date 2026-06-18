"""
SQLite 持久化层
表结构：
  kline         历史 K 线数据
  realtime_cache 实时快照缓存
"""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from config import DB_PATH


# ── Schema ────────────────────────────────────────────────────────────
_DDL = """
CREATE TABLE IF NOT EXISTS kline (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol     TEXT    NOT NULL,
    market     TEXT    NOT NULL,
    freq       TEXT    NOT NULL DEFAULT 'daily',
    date       TEXT    NOT NULL,  -- ISO 8601, e.g. 2024-01-02
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL,
    volume     REAL,
    amount     REAL,
    UNIQUE (symbol, market, freq, date)
);

CREATE TABLE IF NOT EXISTS realtime_cache (
    symbol     TEXT PRIMARY KEY,
    market     TEXT,
    name       TEXT,
    price      REAL,
    change     REAL,
    change_pct REAL,
    volume     REAL,
    updated_at TEXT
);
"""


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    """建表（幂等）"""
    with _conn() as con:
        con.executescript(_DDL)


# ── KLine ─────────────────────────────────────────────────────────────
def upsert_kline(df: pd.DataFrame, symbol: str, market: str, freq: str = "daily") -> int:
    """
    将 DataFrame 写入 kline 表，已存在的行按 (symbol, market, freq, date) 更新。
    返回写入行数。
    """
    if df.empty:
        return 0

    records = []
    for _, row in df.iterrows():
        dt = row["date"]
        if hasattr(dt, "strftime"):
            dt = dt.strftime("%Y-%m-%d")
        records.append((
            symbol, market, freq, str(dt),
            row.get("open"), row.get("high"), row.get("low"),
            row.get("close"), row.get("volume"), row.get("amount"),
        ))

    sql = """
        INSERT INTO kline (symbol, market, freq, date, open, high, low, close, volume, amount)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, market, freq, date) DO UPDATE SET
            open=excluded.open, high=excluded.high, low=excluded.low,
            close=excluded.close, volume=excluded.volume, amount=excluded.amount
    """
    with _conn() as con:
        con.executemany(sql, records)
    return len(records)


def query_kline(
    symbol: str,
    market: str,
    freq: str = "daily",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """从数据库查询 K 线，返回 DataFrame"""
    conditions = ["symbol = ?", "market = ?", "freq = ?"]
    params: list = [symbol, market, freq]
    if start:
        conditions.append("date >= ?")
        params.append(start)
    if end:
        conditions.append("date <= ?")
        params.append(end)

    sql = f"SELECT date, open, high, low, close, volume, amount FROM kline WHERE {' AND '.join(conditions)} ORDER BY date"
    with _conn() as con:
        df = pd.read_sql_query(sql, con, params=params)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


# ── Realtime ──────────────────────────────────────────────────────────
def upsert_realtime(data: dict) -> None:
    sql = """
        INSERT INTO realtime_cache (symbol, market, name, price, change, change_pct, volume, updated_at)
        VALUES (:symbol, :market, :name, :price, :change, :change_pct, :volume, :updated_at)
        ON CONFLICT(symbol) DO UPDATE SET
            market=excluded.market, name=excluded.name, price=excluded.price,
            change=excluded.change, change_pct=excluded.change_pct,
            volume=excluded.volume, updated_at=excluded.updated_at
    """
    data.setdefault("updated_at", datetime.now().isoformat())
    with _conn() as con:
        con.execute(sql, data)


def query_realtime(symbol: str) -> Optional[dict]:
    sql = "SELECT * FROM realtime_cache WHERE symbol = ?"
    with _conn() as con:
        row = con.execute(sql, (symbol,)).fetchone()
    return dict(row) if row else None


# 初始化（模块被 import 时自动建表）
init_db()
