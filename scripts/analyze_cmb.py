import json
import random
import re
import time
import urllib.request
from typing import Optional

import requests


CODE = "600036"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
EM_MIN_INTERVAL = 1.1
_em_last_call = [0.0]


def em_get(url: str, params: Optional[dict] = None, headers: Optional[dict] = None, timeout: int = 15, **kwargs):
    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        return EM_SESSION.get(url, params=params, headers=headers, timeout=timeout, **kwargs)
    finally:
        _em_last_call[0] = time.time()


def tencent_quote(codes: list[str]) -> dict[str, dict]:
    prefixed = []
    for c in codes:
        if c.startswith(("6", "9")):
            prefixed.append(f"sh{c}")
        elif c.startswith("8"):
            prefixed.append(f"bj{c}")
        else:
            prefixed.append(f"sz{c}")

    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")

    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]
        result[code] = {
            "name": vals[1],
            "price": float(vals[3]) if vals[3] else 0,
            "last_close": float(vals[4]) if vals[4] else 0,
            "open": float(vals[5]) if vals[5] else 0,
            "change_amt": float(vals[31]) if vals[31] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "high": float(vals[33]) if vals[33] else 0,
            "low": float(vals[34]) if vals[34] else 0,
            "amount_wan": float(vals[37]) if vals[37] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm": float(vals[39]) if vals[39] else 0,
            "amplitude_pct": float(vals[43]) if vals[43] else 0,
            "mcap_yi": float(vals[44]) if vals[44] else 0,
            "float_mcap_yi": float(vals[45]) if vals[45] else 0,
            "pb": float(vals[46]) if vals[46] else 0,
            "limit_up": float(vals[47]) if vals[47] else 0,
            "limit_down": float(vals[48]) if vals[48] else 0,
            "vol_ratio": float(vals[49]) if vals[49] else 0,
            "pe_static": float(vals[52]) if vals[52] else 0,
        }
    return result


def eastmoney_concept_blocks(code: str) -> dict:
    market_code = 1 if code.startswith("6") else 0
    params = {
        "fltt": "2",
        "invt": "2",
        "secid": f"{market_code}.{code}",
        "spt": "3",
        "pi": "0",
        "pz": "200",
        "po": "1",
        "fields": "f12,f14,f3,f128",
    }
    headers = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}
    try:
        r = em_get("https://push2.eastmoney.com/api/qt/slist/get", params=params, headers=headers, timeout=15)
        d = r.json()
    except Exception as exc:
        return {"error": str(exc), "total": 0, "boards": [], "concept_tags": []}

    diff = (d.get("data") or {}).get("diff") or {}
    items = diff.values() if isinstance(diff, dict) else diff
    boards = [
        {
            "name": it.get("f14", ""),
            "code": it.get("f12", ""),
            "change_pct": it.get("f3", ""),
            "lead_stock": it.get("f128", ""),
        }
        for it in items
    ]
    return {"total": len(boards), "boards": boards, "concept_tags": [b["name"] for b in boards]}


def eastmoney_fund_flow_minute(code: str) -> list[dict]:
    secid = f"1.{code}" if code.startswith("6") else f"0.{code}"
    url = "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
    params = {
        "secid": secid,
        "klt": 1,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
    }
    headers = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/", "Origin": "https://quote.eastmoney.com"}
    try:
        d = em_get(url, params=params, headers=headers, timeout=10).json()
    except Exception:
        return []

    rows = []
    for line in d.get("data", {}).get("klines", []):
        parts = line.split(",")
        if len(parts) >= 6:
            rows.append(
                {
                    "time": parts[0],
                    "main_net": float(parts[1]),
                    "small_net": float(parts[2]),
                    "mid_net": float(parts[3]),
                    "large_net": float(parts[4]),
                    "super_net": float(parts[5]),
                }
            )
    return rows


def stock_fund_flow_120d(code: str) -> list[dict]:
    market_code = 1 if code.startswith("6") else 0
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "secid": f"{market_code}.{code}",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "lmt": "120",
    }
    headers = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/", "Origin": "https://quote.eastmoney.com"}
    try:
        d = em_get(url, params=params, headers=headers, timeout=15).json()
    except Exception:
        return []
    rows = []
    for line in d.get("data", {}).get("klines", []):
        parts = line.split(",")
        if len(parts) >= 7:
            rows.append(
                {
                    "date": parts[0],
                    "main_net": float(parts[1]) if parts[1] != "-" else 0,
                    "small_net": float(parts[2]) if parts[2] != "-" else 0,
                    "mid_net": float(parts[3]) if parts[3] != "-" else 0,
                    "large_net": float(parts[4]) if parts[4] != "-" else 0,
                    "super_net": float(parts[5]) if parts[5] != "-" else 0,
                }
            )
    return rows


def eastmoney_stock_news(code: str, page_size: int = 8) -> list[dict]:
    cb = "jQuery_news"
    url = "https://search-api-web.eastmoney.com/search/jsonp"
    inner_params = json.dumps(
        {
            "uid": "",
            "keyword": code,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                "cmsArticleWebOld": {
                    "searchScope": "default",
                    "sort": "default",
                    "pageIndex": 1,
                    "pageSize": page_size,
                    "preTag": "",
                    "postTag": "",
                }
            },
        },
        separators=(",", ":"),
    )
    params = {"cb": cb, "param": inner_params}
    headers = {"User-Agent": UA, "Referer": "https://so.eastmoney.com/"}
    try:
        text = em_get(url, params=params, headers=headers, timeout=15).text
        json_str = text[text.index("(") + 1 : text.rindex(")")]
        d = json.loads(json_str)
    except Exception:
        return []

    rows = []
    for article in d.get("result", {}).get("cmsArticleWebOld", []) or []:
        rows.append(
            {
                "title": re.sub(r"<[^>]+>", "", article.get("title", "")),
                "content": re.sub(r"<[^>]+>", "", article.get("content", ""))[:160],
                "time": article.get("date", ""),
                "source": article.get("mediaName", ""),
                "url": article.get("url", ""),
            }
        )
    return rows


DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"


def eastmoney_datacenter(
    report_name: str,
    columns: str = "ALL",
    filter_str: str = "",
    page_size: int = 50,
    sort_columns: str = "",
    sort_types: str = "-1",
) -> list[dict]:
    params = {
        "reportName": report_name,
        "columns": columns,
        "filter": filter_str,
        "pageNumber": "1",
        "pageSize": str(page_size),
        "sortColumns": sort_columns,
        "sortTypes": sort_types,
        "source": "WEB",
        "client": "WEB",
    }
    try:
        d = em_get(DATACENTER_URL, params=params, timeout=15).json()
    except Exception:
        return []
    if d.get("result") and d["result"].get("data"):
        return d["result"]["data"]
    return []


def dividend_history(code: str, page_size: int = 8) -> list[dict]:
    data = eastmoney_datacenter(
        "RPT_SHAREBONUS_DET",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="EX_DIVIDEND_DATE",
        sort_types="-1",
    )
    return [
        {
            "date": str(row.get("EX_DIVIDEND_DATE", ""))[:10],
            "bonus_rmb": row.get("PRETAX_BONUS_RMB", 0),
            "transfer_ratio": row.get("TRANSFER_RATIO", 0),
            "bonus_ratio": row.get("BONUS_RATIO", 0),
            "plan": row.get("ASSIGN_PROGRESS", ""),
        }
        for row in data
    ]


def holder_num_change(code: str, page_size: int = 6) -> list[dict]:
    data = eastmoney_datacenter(
        "RPT_HOLDERNUMLATEST",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="END_DATE",
        sort_types="-1",
    )
    return [
        {
            "date": str(row.get("END_DATE", ""))[:10],
            "holder_num": row.get("HOLDER_NUM", 0),
            "change_num": row.get("HOLDER_NUM_CHANGE", 0),
            "change_ratio": row.get("HOLDER_NUM_RATIO", 0),
            "avg_shares": row.get("AVG_FREE_SHARES", 0),
        }
        for row in data
    ]


def margin_trading(code: str, page_size: int = 8) -> list[dict]:
    data = eastmoney_datacenter(
        "RPTA_WEB_RZRQ_GGMX",
        filter_str=f'(SCODE="{code}")',
        page_size=page_size,
        sort_columns="DATE",
        sort_types="-1",
    )
    return [
        {
            "date": str(row.get("DATE", ""))[:10],
            "rzye": row.get("RZYE", 0),
            "rzmre": row.get("RZMRE", 0),
            "rzche": row.get("RZCHE", 0),
            "rqye": row.get("RQYE", 0),
            "rzrqye": row.get("RZRQYE", 0),
        }
        for row in data
    ]


def sina_financial_report(code: str, report_type: str = "lrb", num: int = 6) -> list[dict]:
    prefix = "sh" if code.startswith("6") else "sz"
    url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
    params = {
        "paperCode": f"{prefix}{code}",
        "source": report_type,
        "type": "0",
        "page": "1",
        "num": str(num),
    }
    headers = {"User-Agent": UA}
    try:
        report_list = (
            requests.get(url, params=params, headers=headers, timeout=15)
            .json()
            .get("result", {})
            .get("data", {})
            .get("report_list", {})
            or {}
        )
    except Exception:
        return []

    rows = []
    for period in sorted(report_list.keys(), reverse=True)[:num]:
        obj = report_list[period]
        rec = {"报告期": f"{period[:4]}-{period[4:6]}-{period[6:8]}"}
        for item in obj.get("data", []) or []:
            title = item.get("item_title", "")
            if not title or item.get("item_value") is None:
                continue
            rec[title] = item.get("item_value")
            if item.get("item_tongbi") not in (None, ""):
                rec[f"{title}_同比"] = item.get("item_tongbi")
        rows.append(rec)
    return rows


def summarize_flow(rows: list[dict], windows: tuple[int, ...]) -> dict:
    summary = {}
    for window in windows:
        recent = rows[-window:] if len(rows) >= window else rows
        summary[str(window)] = {
            "days": len(recent),
            "main_net_yi": round(sum(row["main_net"] for row in recent) / 1e8, 3),
            "super_net_yi": round(sum(row["super_net"] for row in recent) / 1e8, 3),
            "positive_main_days": sum(1 for row in recent if row["main_net"] > 0),
        }
    return summary


def main():
    quote = tencent_quote([CODE]).get(CODE, {})
    blocks = eastmoney_concept_blocks(CODE)
    minute_flow = eastmoney_fund_flow_minute(CODE)
    daily_flow = stock_fund_flow_120d(CODE)
    news = eastmoney_stock_news(CODE)
    dividends = dividend_history(CODE)
    holders = holder_num_change(CODE)
    margin = margin_trading(CODE)
    income_statement = sina_financial_report(CODE, "lrb", 6)

    payload = {
        "code": CODE,
        "quote": quote,
        "blocks": {
            "total": blocks.get("total", 0),
            "top": blocks.get("boards", [])[:16],
        },
        "minute_flow": {
            "rows": len(minute_flow),
            "last": minute_flow[-1] if minute_flow else None,
            "sum_main_yi": round(sum(row["main_net"] for row in minute_flow) / 1e8, 3) if minute_flow else None,
        },
        "daily_flow": {
            "rows": len(daily_flow),
            "last_5": daily_flow[-5:],
            "summary": summarize_flow(daily_flow, (5, 10, 20, 60, 120)) if daily_flow else {},
        },
        "news": news[:6],
        "dividends": dividends,
        "holders": holders,
        "margin": margin,
        "income_statement": income_statement,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
