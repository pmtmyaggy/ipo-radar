"""IPO-Radar 主入口.

Usage:
    python -m ipo-radar --dashboard
    python -m ipo-radar --scan
    python -m ipo-radar --scheduler
"""

import sys
import argparse


def main():
    """主函数."""
    parser = argparse.ArgumentParser(
        description="IPO-Radar - IPO决策信息系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="启动仪表盘",
    )
    
    parser.add_argument(
        "--scan",
        action="store_true",
        help="运行每日扫描",
    )
    
    parser.add_argument(
        "--scheduler",
        action="store_true",
        help="启动定时任务调度器",
    )
    
    parser.add_argument(
        "--ticker",
        type=str,
        help="分析单个股票",
    )
    
    parser.add_argument(
        "--setup",
        action="store_true",
        help="初始化项目",
    )
    
    args = parser.parse_args()
    
    if args.setup:
        print("🚀 初始化 IPO-Radar...")
        from src.crawler.models.database import init_database
        init_database()
        print("✅ 初始化完成")
        return 0
    
    if args.dashboard:
        print("🚀 启动仪表盘...")
        import streamlit.web.cli as stcli
        sys.argv = ["streamlit", "run", "src/dashboard/app.py"]
        stcli.main()
        return 0
    
    if args.scan:
        print("🔄 运行每日扫描...")
        from src.scorer.daily_scan import DailyScanner
        scanner = DailyScanner()
        result = scanner.run_scan()
        print(scanner.generate_summary_text(result))
        return 0
    
    if args.scheduler:
        print("⏰ 启动定时任务...")
        from src.scheduler import TaskScheduler
        scheduler = TaskScheduler()
        scheduler.setup_daily_scan("08:30")
        scheduler.setup_intraday_check(15)
        scheduler.setup_post_market_update("16:30")
        scheduler.setup_weekly_update("sunday", "10:00")
        scheduler.start()
        return 0
    
    if args.ticker:
        from src.scorer.composite import SignalAggregator
        aggregator = SignalAggregator()
        report = aggregator.generate_report(args.ticker)
        
        print(f"\n{'='*60}")
        print(f"📊 {args.ticker} 分析报告")
        print(f"{'='*60}")
        print(f"综合信号: {report.overall_signal.value}")
        print(f"基本面评分: {report.fundamental_score}")
        print(f"信号原因: {', '.join(report.signal_reasons)}")
        print(f"{'='*60}\n")
        return 0
    
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
