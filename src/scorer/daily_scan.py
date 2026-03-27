"""每日扫描器 - 对观察名单运行每日扫描.

生成每日投资信号报告。
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict, cast

from src.crawler.models.schemas import CompositeReport, IPOEvent
from src.radar.monitor import IPORadar
from src.scorer.composite import SignalAggregator

logger = logging.getLogger(__name__)


class WindowSummary(TypedDict):
    """窗口摘要."""

    base_detected: bool
    breakout_signal: str | None
    lockup_days_until: int | None
    supply_impact_pct: Any
    earnings_days_until: int | None


class ScanReportDict(TypedDict):
    """扫描报告字典."""

    ticker: str
    company_name: str | None
    ipo_date: str | None
    days_since_ipo: int | None
    current_price: Any
    price_vs_ipo: Any
    fundamental_score: int
    overall_signal: str
    signal_reasons: list[str]
    risk_factors: list[str]
    windows: WindowSummary


@dataclass
class ScanResult:
    """扫描结果."""
    reports: list[ScanReportDict] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)
    scanned_at: datetime = field(default_factory=datetime.now)
    total_count: int = 0
    strong_opportunity_count: int = 0
    opportunity_count: int = 0
    watch_count: int = 0
    no_action_count: int = 0
    source_mode: str = "discovery"
    candidate_tickers: list[str] = field(default_factory=list)
    candidate_source: str = "live"


class DailyScanner:
    """每日扫描器.
    
    默认扫描自动发现的 IPO universe，观察名单扫描单独作为附加模式。
    """

    DISCOVERY_CACHE_PATH = Path("data/discovery_universe_cache.json")

    def __init__(
        self,
        aggregator: SignalAggregator | None = None,
        radar: IPORadar | None = None,
    ):
        """初始化扫描器."""
        self.aggregator = aggregator or SignalAggregator()
        self.radar = radar or IPORadar()
        self.logger = logging.getLogger(__name__)

    def run_scan(
        self,
        tickers: list[str] | None = None,
        mode: str = "discovery",
    ) -> ScanResult:
        """运行每日扫描.
        
        Args:
            tickers: 指定股票列表；传入后忽略 mode
            mode: `discovery` 扫描自动发现的 IPO universe，`watchlist` 扫描手动观察名单
        
        Returns:
            ScanResult扫描结果
        """
        result = ScanResult()
        result.source_mode = mode

        # 获取股票列表
        if tickers is None:
            if mode == "watchlist":
                tickers = self._get_watchlist_tickers()
            else:
                tickers = self._get_discovery_tickers()

        result.total_count = len(tickers)
        result.candidate_tickers = list(tickers)
        self.logger.info(f"Starting {mode} scan for {len(tickers)} stocks")

        # 多线程并发扫描 (方案B：I/O 提速)
        import concurrent.futures

        # 考虑到免费接口的限流策略，max_workers 控制在 5-10
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_ticker = {
                executor.submit(self.aggregator.generate_report, ticker): ticker
                for ticker in tickers
            }

            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    report = future.result()

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
            key=lambda r: priority_order.get(r["overall_signal"], 4)
        )

        self.logger.info(
            f"{mode} scan completed: {result.strong_opportunity_count} strong, "
            f"{result.opportunity_count} opportunity, "
            f"{result.watch_count} watch, "
            f"{len(result.errors)} errors"
        )

        return result

    def run_watchlist_scan(self) -> ScanResult:
        """显式运行观察名单扫描."""
        return self.run_scan(mode="watchlist")

    def _get_watchlist_tickers(self) -> list[str]:
        """获取手动观察名单里的活跃股票."""
        tickers = self.radar.get_active_tickers()
        self.logger.info(f"Watchlist scan candidates loaded: {len(tickers)} tickers")
        return tickers

    def _get_discovery_tickers(self) -> list[str]:
        """从自动发现的 IPO universe 生成扫描候选池."""
        primary_candidates: list[IPOEvent] = []

        try:
            crawler = self.aggregator.crawler
            primary_candidates.extend(crawler.get_upcoming_ipos(days=30))
            primary_candidates.extend(crawler.get_recent_ipos(days=90))
        except Exception as exc:
            self.logger.warning(f"Failed to load discovery IPO candidates: {exc}")
            return []

        tickers = self._extract_scannable_tickers(primary_candidates)
        if tickers:
            self._save_discovery_cache(tickers, source="primary")
            self.logger.info(
                f"Discovery scan candidates loaded from primary source: {len(tickers)} tickers"
            )
            return tickers

        fallback_candidates = self._load_secondary_discovery_candidates()
        tickers = self._extract_scannable_tickers(fallback_candidates)
        if tickers:
            self._save_discovery_cache(tickers, source="secondary")
            self.logger.info(
                f"Discovery scan candidates loaded from fallback source: {len(tickers)} tickers"
            )
            return tickers

        cached = self._load_discovery_cache()
        if cached:
            self.logger.warning(
                f"Discovery live fetch returned no candidates, using cached universe: {len(cached)} tickers"
            )
            return cached

        self.logger.warning("Discovery live fetch returned no candidates and no cache is available")
        return []

    def _load_secondary_discovery_candidates(self) -> list[IPOEvent]:
        """从备用 IPO 源加载候选池."""
        try:
            crawler = self.aggregator.crawler
            ipo_calendar = getattr(crawler, "_ipo_calendar", None)
            if ipo_calendar is None:
                return []
            return cast(list[IPOEvent], ipo_calendar.iposcoop.fetch())
        except Exception as exc:
            self.logger.warning(f"Failed to load secondary discovery candidates: {exc}")
            return []

    def _extract_scannable_tickers(self, candidates: list[IPOEvent]) -> list[str]:
        """从候选事件中提取可扫描 ticker."""
        tickers: list[str] = []
        seen: set[str] = set()
        for event in candidates:
            ticker = event.ticker
            if not ticker:
                continue
            normalized = ticker.upper()
            if not self._is_scannable_event(event):
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            tickers.append(normalized)
        return tickers

    def _is_scannable_ticker(self, ticker: str) -> bool:
        """过滤不适合常规 IPO 扫描的 ticker."""
        normalized = ticker.strip().upper().lstrip("$")

        # 只保留常见普通股 ticker；过滤 unit/right/warrant 等特殊证券
        if not re.fullmatch(r"[A-Z]{1,5}", normalized):
            return False
        if normalized.endswith(("U", "W", "R")) and len(normalized) >= 4:
            return False
        return True

    def _is_scannable_event(self, event: IPOEvent) -> bool:
        """过滤不适合打新扫描的 IPO 事件."""
        ticker = str(event.ticker or "").upper()
        company_name = str(event.company_name or "").lower()

        if not self._is_scannable_ticker(ticker):
            return False

        excluded_name_patterns = (
            "acquisition corp",
            "acquisition corporation",
            "blank check",
            "spac",
            "uplisting",
            "direct listing",
        )
        if any(pattern in company_name for pattern in excluded_name_patterns):
            return False

        return True

    def _save_discovery_cache(self, tickers: list[str], source: str) -> None:
        """保存自动发现 universe 缓存."""
        try:
            self.DISCOVERY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "updated_at": datetime.now().isoformat(),
                "source": source,
                "tickers": tickers,
            }
            self.DISCOVERY_CACHE_PATH.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            self.logger.warning(f"Failed to save discovery cache: {exc}")

    def _load_discovery_cache(self) -> list[str]:
        """读取自动发现 universe 缓存."""
        try:
            if not self.DISCOVERY_CACHE_PATH.exists():
                return []
            payload = json.loads(self.DISCOVERY_CACHE_PATH.read_text(encoding="utf-8"))
            tickers = payload.get("tickers", [])
            if not isinstance(tickers, list):
                return []
            return [str(ticker).upper() for ticker in tickers if str(ticker).strip()]
        except Exception as exc:
            self.logger.warning(f"Failed to load discovery cache: {exc}")
            return []

    def _report_to_dict(self, report: CompositeReport) -> ScanReportDict:
        """将报告转换为字典."""
        return {
            "ticker": report.ticker,
            "company_name": report.company_name,
            "ipo_date": report.ipo_date.isoformat() if report.ipo_date else None,
            "days_since_ipo": report.days_since_ipo,
            "current_price": float(report.current_price) if report.current_price else None,
            "price_vs_ipo": float(report.price_vs_ipo) if report.price_vs_ipo else None,
            "fundamental_score": report.fundamental_score,
            "overall_signal": report.overall_signal.value,
            "signal_reasons": report.signal_reasons,
            "risk_factors": report.risk_factors,
            "windows": {
                "base_detected": report.windows.ipo_base_breakout.base_detected,
                "breakout_signal": report.windows.ipo_base_breakout.breakout_signal,
                "lockup_days_until": report.windows.lockup_expiry.days_until,
                "supply_impact_pct": float(report.windows.lockup_expiry.supply_impact_pct) if report.windows.lockup_expiry.supply_impact_pct else None,
                "earnings_days_until": report.windows.first_earnings.days_until,
            }
        }

    def generate_summary_text(self, result: ScanResult) -> str:
        """生成文本摘要报告.
        
        用于飞书通知和命令行输出。
        """
        lines = [
            "📊 IPO-Radar 每日扫描报告",
            f"生成时间: {result.scanned_at.strftime('%Y-%m-%d %H:%M')}",
            f"扫描股票数: {result.total_count}",
            "",
            f"🎯 强烈机会: {result.strong_opportunity_count}",
            f"📈 有机会: {result.opportunity_count}",
            f"⏰ 观察: {result.watch_count}",
            "",
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
        import decimal
        class DecimalEncoder(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, decimal.Decimal):
                    return float(o)
                return super().default(o)
        return json.dumps(data, indent=2, ensure_ascii=False, cls=DecimalEncoder)

    def get_alerts(self, result: ScanResult) -> list[dict[str, Any]]:
        """获取需要通知的告警.
        
        返回需要发送飞书通知的股票列表。
        """
        alerts: list[dict[str, Any]] = []

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
            lockup_days_until = windows.get("lockup_days_until")
            if lockup_days_until is not None:
                if lockup_days_until <= 3:
                    alerts.append({
                        "level": "medium",
                        "ticker": report["ticker"],
                        "signal": "LOCKUP_IMMINENT",
                        "days_until": lockup_days_until,
                    })

        return alerts


def main() -> int:
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
