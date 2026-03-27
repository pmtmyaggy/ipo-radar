"""Radar CLI."""

import argparse
import sys

from src.crawler.api import CrawlerAPI
from src.radar.monitor import IPORadar


def main() -> int:
    """Run radar commands."""
    parser = argparse.ArgumentParser(description="IPO-Radar 监控工具")
    parser.add_argument("--list", action="store_true", help="列出当前活跃观察名单")
    parser.add_argument("--refresh", action="store_true", help="刷新 IPO 日历并扫描新股")
    args = parser.parse_args()

    crawler = CrawlerAPI()
    radar = IPORadar(crawler=crawler)

    if args.refresh:
        refreshed = crawler.refresh_ipo_calendar()
        new_ipos = radar.scan_new_ipos()
        print(f"Refreshed {refreshed} IPO events")
        print(f"Discovered {len(new_ipos)} new IPOs")
        return 0

    watchlist = radar.get_watchlist(refresh=args.list)
    for item in watchlist:
        print(f"{item.ticker}\t{item.status}\t{item.company_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
