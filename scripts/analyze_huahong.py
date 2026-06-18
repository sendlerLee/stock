import json
import re
import urllib.request
from datetime import datetime

import requests


UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def stock_search(keyword: str, count: int = 10) -> list[dict]:
    url = "https://searchapi.eastmoney.com/api/suggest/get"
    params = {
        "input": keyword,
        "type": 14,
        "token": "D43BF722C8E33BDC906FB84D85E326E8",
        "count": count,
    }
    d = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=10).json()
    suggestions = d.get("QuotationCodeTable", {}).get("Data", [])
    result = []
    for s in suggestions:
        mkt = str(s.get("MktNum", ""))
        market_map = {
            "1": "SH",
            "0": "SZ",
            "105": "NASDAQ",
            "106": "NYSE",
            "107": "US_OTHER",
            "116": "HK",
        }
        result.append(
            {
                "code": s.get("Code"),
                "name": s.get("Name"),
                "mkt_num": s.get("MktNum"),
                "market_name": market_map.get(mkt, mkt),
                "security_type": s.get("SecurityTypeName"),
            }
        )
    return result


def hk_stock_quote_tencent(code: str) -> dict:
    url = f"https://qt.gtimg.cn/q=r_hk{code}"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=10)
    r.encoding = "gbk"
    m = re.search(r'"(.+)"', r.text)
    if not m:
        return {}
    fields = m.group(1).split("~")
    if len(fields) < 57:
        return {}
    return {
        "name": fields[1],
        "name_en": fields[2],
        "price": float(fields[3]) if fields[3] else 0,
        "prev_close": float(fields[4]) if fields[4] else 0,
        "open": float(fields[5]) if fields[5] else 0,
        "high": float(fields[33]) if fields[33] else 0,
        "low": float(fields[34]) if fields[34] else 0,
        "volume": int(float(fields[6])) if fields[6] else 0,
        "amount": float(fields[37]) if fields[37] else 0,
        "change_pct": float(fields[32]) if fields[32] else 0,
        "pe": float(fields[39]) if fields[39] else 0,
        "pb": float(fields[56]) if fields[56] else 0,
        "high_52w": float(fields[35]) if fields[35] else 0,
        "low_52w": float(fields[36]) if fields[36] else 0,
        "market_cap_yi_hkd": float(fields[44]) if fields[44] else 0,
        "timestamp": fields[30],
    }


def a_share_tencent_quote(codes: list[str]) -> dict[str, dict]:
    prefixed = []
    for c in codes:
        prefixed.append(f"sh{c}" if c.startswith(("6", "9")) else f"sz{c}")
    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    data = urllib.request.urlopen(req, timeout=10).read().decode("gbk")
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
            "change_amt": float(vals[31]) if vals[31] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "high": float(vals[33]) if vals[33] else 0,
            "low": float(vals[34]) if vals[34] else 0,
            "amount_wan": float(vals[37]) if vals[37] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm": float(vals[39]) if vals[39] else 0,
            "mcap_yi_cny": float(vals[44]) if vals[44] else 0,
            "pb": float(vals[46]) if vals[46] else 0,
            "pe_static": float(vals[52]) if vals[52] else 0,
        }
    return result


def eastmoney_quote(code: str, mkt_num: int) -> dict:
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "secid": f"{mkt_num}.{code}",
        "fields": "f43,f44,f45,f46,f47,f48,f55,f57,f58,f59,f60,f116,f117,f162,f167,f168,f169,f170",
    }
    d = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=10).json().get("data") or {}
    if not d:
        return {}
    dec = d.get("f59", 2) or 2
    divisor = 10 ** dec

    def price_field(key):
        value = d.get(key)
        if value in (None, "-"):
            return None
        return round(value / divisor, dec)

    def raw_field(key):
        value = d.get(key)
        if value in (None, "-"):
            return None
        return value

    return {
        "code": d.get("f57"),
        "name": d.get("f58"),
        "price": price_field("f43"),
        "high": price_field("f44"),
        "low": price_field("f45"),
        "open": price_field("f46"),
        "volume": raw_field("f47"),
        "amount": raw_field("f48"),
        "prev_close": price_field("f60"),
        "market_cap": raw_field("f116"),
        "float_market_cap": raw_field("f117"),
        "pe_ttm": raw_field("f162"),
        "pb": raw_field("f167"),
        "turnover_pct": raw_field("f168"),
        "change_amt": price_field("f169"),
        "change_pct": raw_field("f170"),
    }


def a_share_concept_blocks(code: str) -> dict:
    params = {
        "fltt": "2",
        "invt": "2",
        "secid": f"1.{code}" if code.startswith("6") else f"0.{code}",
        "spt": "3",
        "pi": "0",
        "pz": "200",
        "po": "1",
        "fields": "f12,f14,f3,f128",
    }
    d = requests.get(
        "https://push2.eastmoney.com/api/qt/slist/get",
        params=params,
        headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"},
        timeout=15,
    ).json()
    diff = (d.get("data") or {}).get("diff") or {}
    items = diff.values() if isinstance(diff, dict) else diff
    boards = [
        {
            "name": item.get("f14", ""),
            "code": item.get("f12", ""),
            "change_pct": item.get("f3", ""),
            "lead_stock": item.get("f128", ""),
        }
        for item in items
    ]
    return {"total": len(boards), "top": boards[:16], "tags": [item["name"] for item in boards]}


def a_share_fund_flow_120d(code: str) -> dict:
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "secid": f"1.{code}" if code.startswith("6") else f"0.{code}",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "lmt": "120",
    }
    d = requests.get(
        url,
        params=params,
        headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"},
        timeout=15,
    ).json()
    rows = []
    for line in d.get("data", {}).get("klines", []):
        parts = line.split(",")
        if len(parts) >= 6:
            rows.append(
                {
                    "date": parts[0],
                    "main_net": float(parts[1]) if parts[1] != "-" else 0,
                    "super_net": float(parts[5]) if parts[5] != "-" else 0,
                }
            )
    summary = {}
    for window in (5, 10, 20, 60, 120):
        recent = rows[-window:]
        summary[str(window)] = {
            "days": len(recent),
            "main_net_yi": round(sum(item["main_net"] for item in recent) / 1e8, 3),
            "super_net_yi": round(sum(item["super_net"] for item in recent) / 1e8, 3),
            "positive_days": sum(1 for item in recent if item["main_net"] > 0),
        }
    return {"rows": len(rows), "last_5": rows[-5:], "summary": summary}


def stock_kline_yahoo(symbol: str, interval: str = "1d", range_: str = "6mo") -> list[dict]:
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"interval": interval, "range": range_}
    d = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15).json()
    chart = d.get("chart", {}).get("result", [{}])[0]
    timestamps = chart.get("timestamp", [])
    quote = chart.get("indicators", {}).get("quote", [{}])[0]
    rows = []
    for i, ts in enumerate(timestamps):
        close = quote["close"][i]
        if close is None:
            continue
        rows.append(
            {
                "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                "open": round(quote["open"][i], 2) if quote["open"][i] else 0,
                "high": round(quote["high"][i], 2) if quote["high"][i] else 0,
                "low": round(quote["low"][i], 2) if quote["low"][i] else 0,
                "close": round(close, 2),
                "volume": int(quote["volume"][i]) if quote["volume"][i] else 0,
            }
        )
    return rows


def trend_summary(rows: list[dict]) -> dict:
    if not rows:
        return {}
    closes = [row["close"] for row in rows]
    last = closes[-1]
    first = closes[0]
    ma20 = sum(closes[-20:]) / min(len(closes), 20)
    ma60 = sum(closes[-60:]) / min(len(closes), 60)
    return {
        "rows": len(rows),
        "first_date": rows[0]["date"],
        "last_date": rows[-1]["date"],
        "last_close": round(last, 2),
        "range_return_pct": round((last / first - 1) * 100, 2) if first else None,
        "ma20": round(ma20, 2),
        "ma60": round(ma60, 2),
        "above_ma20": last > ma20,
        "above_ma60": last > ma60,
    }


def main():
    hk_kline = stock_kline_yahoo("1347.HK", "1d", "6mo")
    payload = {
        "search_huahong": stock_search("华虹", 10),
        "hk_01347": hk_stock_quote_tencent("01347"),
        "hk_01347_eastmoney": eastmoney_quote("01347", 116),
        "hk_01347_trend_6mo": trend_summary(hk_kline),
        "hk_01347_kline_last_5": hk_kline[-5:],
        "a_688347": a_share_tencent_quote(["688347"]).get("688347", {}),
        "a_688347_eastmoney": eastmoney_quote("688347", 1),
        "a_688347_blocks": a_share_concept_blocks("688347"),
        "a_688347_fund_flow": a_share_fund_flow_120d("688347"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
