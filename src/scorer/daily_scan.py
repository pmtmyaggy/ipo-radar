"""每日扫描器 - 对观察名单运行每日扫描.

生成每日投资信号报告。
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional

from src.scorer.composite import SignalAggregator, CompositeScorer
from src.radar.monitor import IPORadar
from src.crawler.api import CrawlerAPI

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """扫描结果."""
    reports: List[dict] = field(default_factory=list)
    errors: List[tuple] = field(default_factory=list)
    scanned_at: datetime = field(default_factory=datetime.now)
    total_count: int = 0
    strong_opportunity_count: int = 0
    opportunity_count: int = 0
    watch_count: int = 0
    no_action_count: int = 0


class DailyScanner:
    """每日扫描器.
    
    对观察名单中所有股票运行完整扫描。
    """
    
    def __init__(
        self,
        aggregator: Optional[SignalAggregator] = None,
        radar: Optional[IPORadar] = None,
    ):
        """初始化扫描器."""
        self.aggregator = aggregator or SignalAggregator()
        self.radar = radar or IPORadar()
        self.logger = logging.getLogger(__name__)
    
    def run_scan(self, tickers: Optional[List[str]] = None) -> ScanResult:
        """运行每日扫描.
        
        Args:
            tickers: 指定股票列表，None则扫描观察名单
        
        Returns:
            ScanResult扫描结果
        """
        result = ScanResult()
        
        # 获取股票列表
        if tickers is None:
            tickers = self.radar.get_active_tickers()
        
        result.total_count = len(tickers)
        self.logger.info(f"Starting daily scan for {len(tickers)} stocks")
        
        # 逐个扫描
        for ticker in tickers:
            try:
                report = self.aggregator.generate_report(ticker)
                
                # 转换为字典
                report_dict = self._report_to_dict(report)
                result.reports.append(report_dict)
                
                # 统计
                if report.overall_signal.value == "STRONG_OPPORTUNITY":
                    result.strong_opportunity_count += 1
                elif report.overall_signal.value == "OPPORTUNITY":
                    result.opportunity_count += 1
                elif report.overall_signal.value == "WATCH":
                    result.watch_count += 1
                else:
                    result.no_action_count += 1
                    
            except Exception as e:
                self.logger.error(f"Error scanning {ticker}: {e}")
                result.errors.append((ticker, str(e)))
        
        # 按信号强度排序
        priority_order = {
            "STRONG_OPPORTUNITY": 0,
            "OPPORTUNITY": 1,
            "WATCH": 2,
            "NO_ACTION": 3
        }
        result.reports.sort(
            key=lambda r: priority_order.get(r.get("overall_signal"), 4)
        )
        
        self.logger.info(
            f"Scan completed: {result.strong_opportunity_count} strong, "
            f"{result.opportunity_count} opportunity, "
            f"{result.watch_count} watch, "
            f"{len(result.errors)} errors"
        )
        
        return result
    
    def _report_to_dict(self, report) -> dict:
        """将报告转换为字典."""
        return {
            "ticker": report.ticker,
            "company_name": report.company_name,
            "ipo_date": report.ipo_date.isoformat() if report.ipo_date else None,
            "days_since_ipo": report.days_since_ipo,
            "current_price": report.current_price,
            "price_vs_ipo": report.price_vs_ipo,
            "fundamental_score": report.fundamental_score,
            "overall_signal": report.overall_signal.value,
            "signal_reasons": report.signal_reasons,
            "risk_factors": report.risk_factors,
            "windows": {
                "base_detected": report.windows.ipo_base_breakout.base_detected,
                "breakout_signal": report.windows.ipo_base_breakout.breakout_signal,
                "lockup_days_until": report.windows.lockup_expiry.days_until,
                "earnings_days_until": report.windows.first_earnings.days_until,
            }
        }
    
    def generate_summary_text(self, result: ScanResult) -> str:
        """生成文本摘要报告.
        
        用于飞书通知和命令行输出。
        """
        lines = [
            f"📊 IPO-Radar 每日扫描报告",
            f"生成时间: {result.scanned_at.strftime('%Y-%m-%d %H:%M')}",
            f"扫描股票数: {result.total_count}",
            f"",
            f"🎯 强烈机会: {result.strong_opportunity_count}",
            f"📈 有机会: {result.opportunity_count}",
            f"⏰ 观察: {result.watch_count}",
            f"",
            "=" * 50,
        ]
        
        # 强烈机会
        if result.strong_opportunity_count > 0:
            lines.extend(["", "🔥 强烈机会股票:"])
            for report in result.reports:
                if report.get("overall_signal") == "STRONG_OPPORTUNITY":
                    lines.append(
                        f"  🚨 {report['ticker']}: "
                        f"当前价 ${report.get('current_price', 'N/A')}, "
                        f"基本面 {report.get('fundamental_score', 'N/A')}/100"
                    )
                    for reason in report.get('signal_reasons', []):
                        lines.append(f"     └─ {reason}")
        
        # 有机会
        if result.opportunity_count > 0:
            lines.extend(["", "📈 有机会股票:"])
            for report in result.reports:
                if report.get("overall_signal") == "OPPORTUNITY":
                    lines.append(f"  ✅ {report['ticker']}")
                    for reason in report.get('signal_reasons', []):
                        lines.append(f"     └─ {reason}")
        
        # 错误
        if result.errors:
            lines.extend(["", f"⚠️ 错误 ({len(result.errors)}):"])
            for ticker, error in result.errors[:5]:  # 只显示前5个
                lines.append(f"  {ticker}: {error}")
        
        lines.append("")
        lines.append("=" * 50)
        
        return "\n".join(lines)
    
    def generate_json_report(self, result: ScanResult) -> str:
        """生成JSON格式报告."""
        data = {
            "scanned_at": result.scanned_at.isoformat(),
            "total_count": result.total_count,
            "summary": {
                "strong_opportunity": result.strong_opportunity_count,
                "opportunity": result.opportunity_count,
                "watch": result.watch_count,
                "no_action": result.no_action_count,
                "errors": len(result.errors),
            },
            "reports": result.reports,
            "errors": [{"ticker": t, "error": e} for t, e in result.errors],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    def get_alerts(self, result: ScanResult) -> List[dict]:
        """获取需要通知的告警.
        
        返回需要发送飞书通知的股票列表。
        """
        alerts = []
        
        for report in result.reports:
            signal = report.get("overall_signal")
            
            # 强烈机会和突破信号需要通知
            if signal in ["STRONG_OPPORTUNITY"]:
                alerts.append({
                    "level": "high",
                    "ticker": report["ticker"],
                    "signal": signal,
                    "reasons": report.get("signal_reasons", []),
                })
            
            # 禁售期3天内通知
            windows = report.get("windows", {})
            if windows.get("lockup_days_until") is not None:
                if windows["lockup_days_until"] <= 3:
                    alerts.append({
                        "level": "medium",
                        "ticker": report["ticker"],
                        "signal": "LOCKUP_IMMINENT",
                        "days_until": windows["lockup_days_until"],
                    })
        
        return alerts


def main():
    """CLI入口."""
    import sys
    
    print("🚀 IPO-Radar 每日扫描")
    print("=" * 50)
    
    scanner = DailyScanner()
    result = scanner.run_scan()
    
    # 打印摘要
    print(scanner.generate_summary_text(result))
    
    # 保存JSON报告
    if len(sys.argv) > 1 and sys.argv[1] == "--save":
        json_report = scanner.generate_json_report(result)
        filename = f"scan_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(filename, "w") as f:
            f.write(json_report)
        print(f"\n报告已保存: {filename}")
    
    return 0 if not result.errors else 1


if __name__ == "__main__":
    exit(main())
