"""Scorer CLI - 命令行入口.

Usage:
    python -m src.scorer --ticker CAVA
    python -m src.scorer --scan
    python -m src.scorer --scan --save
"""

import argparse
import sys
from datetime import datetime

from src.scorer.composite import SignalAggregator
from src.scorer.daily_scan import DailyScanner


def format_report(report) -> str:
    """格式化报告为可读文本."""
    lines = [
        f"\n{'='*60}",
        f"📊 IPO-Radar 综合评分报告",
        f"{'='*60}",
        f"",
        f"股票代码: {report.ticker}",
    ]
    
    if report.company_name:
        lines.append(f"公司名称: {report.company_name}")
    
    if report.ipo_date:
        lines.append(f"IPO日期: {report.ipo_date}")
    
    if report.days_since_ipo:
        lines.append(f"上市天数: {report.days_since_ipo} 天")
    
    lines.append(f"")
    
    # 价格信息
    if report.current_price:
        lines.append(f"当前价格: ${report.current_price:.2f}")
    
    if report.ipo_price and report.price_vs_ipo:
        change_pct = (report.price_vs_ipo - 1) * 100
        lines.append(f"vs IPO: {change_pct:+.1f}%")
    
    lines.append(f"")
    
    # 基本面评分
    lines.append(f"基本面评分: {report.fundamental_score}/100")
    lines.append(f"")
    
    # 四窗口状态
    lines.append(f"四窗口状态:")
    
    # 底部突破
    base = report.windows.ipo_base_breakout
    if base.base_detected:
        lines.append(f"  📐 底部形态: 检测到")
        if base.breakout_signal:
            lines.append(f"     └─ 突破信号: {base.breakout_signal}")
    else:
        lines.append(f"  📐 底部形态: 未形成")
    
    # 禁售期
    lockup = report.windows.lockup_expiry
    if lockup.days_until is not None:
        lines.append(f"  🔒 禁售期: {lockup.days_until} 天后到期")
        if lockup.supply_impact_pct:
            lines.append(f"     └─ 供应冲击: {lockup.supply_impact_pct:.1%}")
    
    # 财报
    earnings = report.windows.first_earnings
    if earnings.days_until is not None:
        lines.append(f"  📈 首次财报: {earnings.days_until} 天后")
        if earnings.earnings_signal:
            lines.append(f"     └─ 信号: {earnings.earnings_signal}")
    
    lines.append(f"")
    
    # 综合信号
    signal_emoji = {
        "STRONG_OPPORTUNITY": "🎯",
        "OPPORTUNITY": "📈",
        "WATCH": "👀",
        "NO_ACTION": "➖",
    }
    emoji = signal_emoji.get(report.overall_signal.value, "❓")
    lines.append(f"综合信号: {emoji} {report.overall_signal.value}")
    lines.append(f"")
    
    # 信号原因
    if report.signal_reasons:
        lines.append(f"信号原因:")
        for reason in report.signal_reasons:
            lines.append(f"  ✓ {reason}")
        lines.append(f"")
    
    # 风险因素
    if report.risk_factors:
        lines.append(f"⚠️ 风险因素:")
        for risk in report.risk_factors:
            lines.append(f"  • {risk}")
        lines.append(f"")
    
    lines.append(f"生成时间: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"{'='*60}\n")
    
    return "\n".join(lines)


def main():
    """主函数."""
    parser = argparse.ArgumentParser(
        description="IPO-Radar 综合评分工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --ticker CAVA          # 单个股票评分
  %(prog)s --scan                 # 每日扫描
  %(prog)s --scan --save          # 扫描并保存报告
        """
    )
    
    parser.add_argument(
        "--ticker",
        type=str,
        help="分析单个股票，如 CAVA",
    )
    
    parser.add_argument(
        "--scan",
        action="store_true",
        help="运行每日扫描",
    )
    
    parser.add_argument(
        "--save",
        action="store_true",
        help="保存扫描报告为JSON",
    )
    
    parser.add_argument(
        "--tickers",
        nargs="+",
        help="指定扫描的股票列表",
    )
    
    args = parser.parse_args()
    
    # 单个股票评分
    if args.ticker:
        print(f"🔍 正在分析 {args.ticker.upper()}...")
        
        aggregator = SignalAggregator()
        report = aggregator.generate_report(args.ticker)
        
        print(format_report(report))
        return 0
    
    # 每日扫描
    if args.scan:
        print("🚀 IPO-Radar 每日扫描")
        print("=" * 60)
        
        scanner = DailyScanner()
        
        tickers = args.tickers if args.tickers else None
        result = scanner.run_scan(tickers)
        
        # 打印摘要
        print(scanner.generate_summary_text(result))
        
        # 保存报告
        if args.save:
            import json
            json_report = scanner.generate_json_report(result)
            filename = f"scan_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(filename, "w", encoding="utf-8") as f:
                f.write(json_report)
            
            print(f"\n💾 报告已保存: {filename}")
        
        return 0 if not result.errors else 1
    
    # 默认显示帮助
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
