"""Fundamental screener CLI."""

import argparse
import sys

from src.screener.fundamentals import FundamentalScreener


def main() -> int:
    """Run screener commands."""
    parser = argparse.ArgumentParser(description="IPO-Radar 基本面筛选工具")
    parser.add_argument("--ticker", type=str, help="分析单个股票")
    args = parser.parse_args()

    if not args.ticker:
        parser.print_help()
        return 0

    screener = FundamentalScreener()
    score = screener.score_ipo(args.ticker.upper())
    print(f"{score.ticker}: {score.total}/100 ({score.verdict})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
