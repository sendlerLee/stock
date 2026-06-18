import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import Market
from src.agent import AgentMode, AsOfStockDataProvider, SnapshotBuilder, StockScanner, StockTarget, format_report


UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def yesterday() -> date:
    return date.today() - timedelta(days=1)


def discover_a_share_universe(limit: int = 30) -> list[StockTarget]:
    """Discover a small liquid A-share universe from Eastmoney clist."""
    rows = []
    rows.extend(eastmoney_a_list(sort_field="f6", sort_desc=True, page_size=max(limit, 50)))
    rows.extend(eastmoney_a_list(sort_field="f3", sort_desc=True, page_size=max(limit // 2, 20)))
    rows.extend(eastmoney_a_list(sort_field="f3", sort_desc=False, page_size=max(limit // 2, 20)))

    seen = set()
    targets = []
    for row in rows:
        code = row.get("code")
        name = row.get("name") or ""
        if not code or code in seen:
            continue
        if name.startswith(("退市", "ST", "*ST")):
            continue
        seen.add(code)
        notes = [
            f"discovered_by={row.get('source')}",
            f"discovery_change_pct={row.get('change_pct')}",
            f"discovery_amount={row.get('amount')}",
        ]
        targets.append(StockTarget(Market.A, code, name=name, notes=notes))
        if len(targets) >= limit:
            break
    return targets


def eastmoney_a_list(sort_field: str, sort_desc: bool, page_size: int = 50) -> list[dict[str, Any]]:
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": str(page_size),
        "po": "1" if sort_desc else "0",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": sort_field,
        "fs": "m:1+t:2,m:1+t:23,m:0+t:6,m:0+t:80",
        "fields": "f2,f3,f5,f6,f12,f14,f15,f16,f17,f18",
    }
    data = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15).json()
    rows = []
    for item in data.get("data", {}).get("diff", []) or []:
        rows.append(
            {
                "code": item.get("f12"),
                "name": item.get("f14"),
                "price": item.get("f2"),
                "change_pct": item.get("f3"),
                "volume": item.get("f5"),
                "amount": item.get("f6"),
                "source": f"{sort_field}_{'desc' if sort_desc else 'asc'}",
            }
        )
    return rows


def write_outputs(result, targets: list[StockTarget], as_of: date, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"stock_agent_report_{as_of.isoformat()}.json"
    md_path = output_dir / f"stock_agent_report_{as_of.isoformat()}.md"

    payload = result.to_dict()
    payload["as_of"] = as_of.isoformat()
    payload["universe"] = [asdict(target) for target in targets]
    payload["note"] = "K-line/realtime fields are clipped to as_of; fundamentals may use latest free endpoint data."
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Stock Agent Daily Report - {as_of.isoformat()}",
        "",
        "Note: K-line/realtime fields are clipped to the report date; some fundamentals use latest available free endpoint data.",
        "",
        f"Universe size: {len(targets)}",
        "",
        "## Summary",
        "",
        format_report(result),
        "",
        "## Universe",
        "",
    ]
    for target in targets:
        lines.append(f"- {target.market.value}:{target.symbol} {target.name}")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def parse_args():
    parser = argparse.ArgumentParser(description="Generate daily stock-agent report")
    parser.add_argument("--as-of", default=yesterday().isoformat(), help="Report date, YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=30, help="Max discovered A-share targets")
    parser.add_argument("--symbols", help="Optional explicit targets, e.g. A:600036,A:688347")
    parser.add_argument("--mode", choices=[m.value for m in AgentMode], default=AgentMode.TRADING.value)
    parser.add_argument("--output-dir", default="reports")
    return parser.parse_args()


def main():
    args = parse_args()
    as_of = date.fromisoformat(args.as_of)
    if args.symbols:
        targets = [StockTarget.parse(item.strip()) for item in args.symbols.split(",") if item.strip()]
    else:
        targets = discover_a_share_universe(args.limit)
    provider = AsOfStockDataProvider(as_of=as_of)
    scanner = StockScanner(builder=SnapshotBuilder(provider=provider))
    result = scanner.scan(targets, mode=AgentMode(args.mode), days=180)
    json_path, md_path = write_outputs(result, targets, as_of, Path(args.output_dir))

    print(format_report(result))
    print("")
    print(f"Wrote JSON: {json_path}")
    print(f"Wrote Markdown: {md_path}")


if __name__ == "__main__":
    main()
