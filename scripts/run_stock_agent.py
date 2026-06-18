import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.agent import AgentMode, StockScanner, StockTarget, format_report


SAMPLE_TARGETS = [
    StockTarget.parse("A:600036"),
    StockTarget.parse("A:688347"),
    StockTarget.parse("HK:01347"),
]


def parse_args():
    parser = argparse.ArgumentParser(description="Run stock selection agent")
    parser.add_argument("--symbols", help="Comma-separated targets, e.g. A:600036,HK:01347,US:AAPL")
    parser.add_argument("--sample", action="store_true", help="Use built-in sample universe")
    parser.add_argument("--mode", choices=[m.value for m in AgentMode], default=AgentMode.TRADING.value)
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--json", action="store_true", help="Output structured JSON")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.sample:
        targets = SAMPLE_TARGETS
    elif args.symbols:
        targets = [StockTarget.parse(item.strip()) for item in args.symbols.split(",") if item.strip()]
    else:
        raise SystemExit("Provide --sample or --symbols MARKET:SYMBOL,...")

    result = StockScanner().scan(targets, mode=AgentMode(args.mode), days=args.days)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_report(result))


if __name__ == "__main__":
    main()
