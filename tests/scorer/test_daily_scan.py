"""每日扫描器测试."""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch

from src.scorer.daily_scan import DailyScanner, ScanResult
from src.crawler.models.schemas import (
    OverallSignal,
    WindowsStatus,
)


class TestScanResult:
    """测试扫描结果类."""

    def test_default_values(self):
        """测试默认值."""
        result = ScanResult()
        
        assert result.reports == []
        assert result.errors == []
        assert result.total_count == 0
        assert result.strong_opportunity_count == 0
        assert result.opportunity_count == 0
        assert result.watch_count == 0
        assert result.no_action_count == 0
        assert isinstance(result.scanned_at, datetime)


class TestDailyScanner:
    """测试每日扫描器."""

    @pytest.fixture
    def mock_aggregator(self):
        """创建模拟聚合器."""
        mock = Mock()
        
        def create_report(ticker):
            report = Mock()
            report.ticker = ticker
            report.company_name = "Test Company"
            report.ipo_date = None
            report.days_since_ipo = 30
            report.current_price = 50.0
            report.price_vs_ipo = 1.25
            report.fundamental_score = 75
            report.overall_signal = OverallSignal.OPPORTUNITY
            report.signal_reasons = ["Test reason"]
            report.risk_factors = []
            report.windows = WindowsStatus()
            return report
        
        mock.generate_report.side_effect = create_report
        return mock

    @pytest.fixture
    def mock_radar(self):
        """创建模拟雷达."""
        mock = Mock()
        mock.get_active_tickers.return_value = ["TEST", "ABC", "XYZ"]
        return mock

    @pytest.fixture
    def scanner(self, mock_aggregator, mock_radar):
        """创建扫描器实例."""
        return DailyScanner(aggregator=mock_aggregator, radar=mock_radar)

    def test_run_scan_with_tickers(self, scanner, mock_aggregator):
        """测试指定股票列表扫描."""
        result = scanner.run_scan(tickers=["A", "B"])
        
        assert result.total_count == 2
        assert len(result.reports) == 2
        assert mock_aggregator.generate_report.call_count == 2

    def test_run_scan_with_watchlist(self, scanner, mock_aggregator, mock_radar):
        """测试显式使用观察名单扫描."""
        result = scanner.run_scan(mode="watchlist")
        
        assert result.total_count == 3
        assert len(result.reports) == 3
        mock_radar.get_active_tickers.assert_called_once()

    def test_run_scan_uses_discovery_universe_by_default(self, scanner):
        """测试默认扫描自动发现的 IPO universe."""
        scanner.aggregator.crawler.get_upcoming_ipos.return_value = [
            Mock(ticker="CAVA"),
            Mock(ticker="FMACU"),
        ]
        scanner.aggregator.crawler.get_recent_ipos.return_value = [
            Mock(ticker="ARM"),
            Mock(ticker="QADRU"),
            Mock(ticker="CAVA"),
        ]

        result = scanner.run_scan()

        assert result.total_count == 2
        assert [report["ticker"] for report in result.reports] == ["CAVA", "ARM"]
        scanner.radar.get_active_tickers.assert_not_called()

    def test_run_scan_uses_secondary_source_when_primary_only_has_unscannable_events(self, scanner):
        """测试主源只有不可扫描标的时回退到备用源."""
        scanner.aggregator.crawler.get_upcoming_ipos.return_value = [
            Mock(ticker="FMACU", company_name="Future Money Acquisition Corp"),
        ]
        scanner.aggregator.crawler.get_recent_ipos.return_value = [
            Mock(ticker="QADRU", company_name="QDRO Acquisition Corp."),
        ]

        mock_ipo_calendar = Mock()
        mock_ipo_calendar.iposcoop.fetch.return_value = [
            Mock(ticker="HIFI", company_name="Hillhouse Frontier Holdings"),
            Mock(ticker="TMCR", company_name="Metals Royalty Co. (The)(NASDAQ Direct Listing)"),
            Mock(ticker="SEAH", company_name="Seahawk Recycling Holdings, Inc."),
        ]
        scanner.aggregator.crawler._ipo_calendar = mock_ipo_calendar

        result = scanner.run_scan()

        assert result.total_count == 2
        assert [report["ticker"] for report in result.reports] == ["HIFI", "SEAH"]

    def test_run_scan_signal_counting(self, scanner):
        """测试信号计数."""
        # 创建不同信号的报告
        def create_report_with_signal(ticker):
            signal_map = {
                "A": OverallSignal.STRONG_OPPORTUNITY,
                "B": OverallSignal.OPPORTUNITY,
                "C": OverallSignal.WATCH,
                "D": OverallSignal.NO_ACTION,
            }
            report = Mock()
            report.ticker = ticker
            report.company_name = None
            report.ipo_date = None
            report.days_since_ipo = None
            report.current_price = None
            report.price_vs_ipo = None
            report.fundamental_score = None
            report.overall_signal = signal_map.get(ticker, OverallSignal.NO_ACTION)
            report.signal_reasons = []
            report.risk_factors = []
            report.windows = WindowsStatus()
            return report
        
        scanner.aggregator.generate_report.side_effect = create_report_with_signal
        
        result = scanner.run_scan(tickers=["A", "B", "C", "D"])
        
        assert result.strong_opportunity_count == 1
        assert result.opportunity_count == 1
        assert result.watch_count == 1
        assert result.no_action_count == 1

    def test_run_scan_error_handling(self, scanner, mock_aggregator):
        """测试错误处理."""
        # 第一个成功，第二个失败
        def create_report_or_error(ticker):
            if ticker == "B":
                raise Exception("API Error")
            report = Mock()
            report.ticker = ticker
            report.company_name = "Test"
            report.ipo_date = None
            report.days_since_ipo = None
            report.current_price = None
            report.price_vs_ipo = None
            report.fundamental_score = None
            report.overall_signal = OverallSignal.OPPORTUNITY
            report.signal_reasons = []
            report.risk_factors = []
            report.windows = WindowsStatus()
            return report
        
        mock_aggregator.generate_report.side_effect = create_report_or_error
        
        result = scanner.run_scan(tickers=["A", "B"])
        
        assert len(result.reports) == 1
        assert result.reports[0]["ticker"] == "A"
        assert len(result.errors) == 1
        assert result.errors[0] == ("B", "API Error")

    def test_run_scan_priority_sorting(self, scanner):
        """测试报告按优先级排序."""
        def create_report_with_signal(ticker):
            signal_map = {
                "A": OverallSignal.NO_ACTION,
                "B": OverallSignal.STRONG_OPPORTUNITY,
                "C": OverallSignal.WATCH,
                "D": OverallSignal.OPPORTUNITY,
            }
            report = Mock()
            report.ticker = ticker
            report.company_name = None
            report.ipo_date = None
            report.days_since_ipo = None
            report.current_price = None
            report.price_vs_ipo = None
            report.fundamental_score = None
            report.overall_signal = signal_map.get(ticker, OverallSignal.NO_ACTION)
            report.signal_reasons = []
            report.risk_factors = []
            report.windows = WindowsStatus()
            return report
        
        scanner.aggregator.generate_report.side_effect = create_report_with_signal
        
        result = scanner.run_scan(tickers=["A", "B", "C", "D"])
        
        # 验证排序：STRONG_OPPORTUNITY 应该排在第一位
        assert result.reports[0]["overall_signal"] == "STRONG_OPPORTUNITY"
        assert result.reports[1]["overall_signal"] == "OPPORTUNITY"
        assert result.reports[2]["overall_signal"] == "WATCH"
        assert result.reports[3]["overall_signal"] == "NO_ACTION"

    def test_report_to_dict(self, scanner):
        """测试报告转字典."""
        windows = WindowsStatus()
        windows.ipo_base_breakout.base_detected = True
        windows.ipo_base_breakout.breakout_signal = "strong"
        windows.lockup_expiry.days_until = 20
        windows.first_earnings.days_until = 15
        
        report = Mock()
        report.ticker = "TEST"
        report.company_name = "Test Co"
        report.ipo_date = None
        report.days_since_ipo = 30
        report.current_price = 50.0
        report.price_vs_ipo = 1.25
        report.fundamental_score = 75
        report.overall_signal = OverallSignal.OPPORTUNITY
        report.signal_reasons = ["Good signal"]
        report.risk_factors = ["Some risk"]
        report.windows = windows
        
        result_dict = scanner._report_to_dict(report)
        
        assert result_dict["ticker"] == "TEST"
        assert result_dict["fundamental_score"] == 75
        assert result_dict["overall_signal"] == "OPPORTUNITY"
        assert result_dict["signal_reasons"] == ["Good signal"]
        assert result_dict["windows"]["base_detected"] is True
        assert result_dict["windows"]["breakout_signal"] == "strong"

    def test_generate_summary_text(self, scanner):
        """测试生成文本摘要."""
        result = ScanResult()
        result.total_count = 5
        result.strong_opportunity_count = 1
        result.opportunity_count = 2
        result.watch_count = 1
        result.scanned_at = datetime(2024, 1, 15, 9, 30)
        
        # 添加报告
        result.reports = [
            {
                "ticker": "STRONG",
                "overall_signal": "STRONG_OPPORTUNITY",
                "current_price": 100.0,
                "fundamental_score": 85,
                "signal_reasons": ["Strong breakout"],
            },
            {
                "ticker": "OPPORTUNITY1",
                "overall_signal": "OPPORTUNITY",
                "signal_reasons": ["Good setup"],
            },
            {
                "ticker": "OPPORTUNITY2",
                "overall_signal": "OPPORTUNITY",
                "signal_reasons": ["Breakout pending"],
            },
        ]
        
        text = scanner.generate_summary_text(result)
        
        assert "IPO-Radar 每日扫描报告" in text
        assert "强烈机会: 1" in text
        assert "有机会: 2" in text
        assert "STRONG" in text
        assert "Strong breakout" in text

    def test_generate_summary_text_with_errors(self, scanner):
        """测试生成摘要包含错误."""
        result = ScanResult()
        result.total_count = 3
        result.errors = [("FAILED", "API timeout")]
        result.scanned_at = datetime.now()
        result.reports = []
        
        text = scanner.generate_summary_text(result)
        
        assert "错误 (1)" in text
        assert "FAILED: API timeout" in text

    def test_generate_json_report(self, scanner):
        """测试生成JSON报告."""
        result = ScanResult()
        result.total_count = 2
        result.strong_opportunity_count = 1
        result.opportunity_count = 1
        result.watch_count = 0
        result.no_action_count = 0
        result.scanned_at = datetime(2024, 1, 15, 9, 30)
        result.reports = [{"ticker": "TEST", "signal": "STRONG"}]
        result.errors = []
        
        json_str = scanner.generate_json_report(result)
        
        data = json.loads(json_str)
        assert data["total_count"] == 2
        assert data["summary"]["strong_opportunity"] == 1
        assert data["reports"][0]["ticker"] == "TEST"

    def test_get_alerts_strong_opportunity(self, scanner):
        """测试获取告警 - 强烈机会."""
        result = ScanResult()
        result.reports = [
            {
                "ticker": "ALERT",
                "overall_signal": "STRONG_OPPORTUNITY",
                "signal_reasons": ["Breakout confirmed"],
                "windows": {},
            }
        ]
        
        alerts = scanner.get_alerts(result)
        
        assert len(alerts) == 1
        assert alerts[0]["level"] == "high"
        assert alerts[0]["ticker"] == "ALERT"

    def test_get_alerts_lockup_imminent(self, scanner):
        """测试获取告警 - 禁售期临近."""
        result = ScanResult()
        result.reports = [
            {
                "ticker": "LOCKUP",
                "overall_signal": "WATCH",
                "windows": {"lockup_days_until": 2},
            }
        ]
        
        alerts = scanner.get_alerts(result)
        
        assert len(alerts) == 1
        assert alerts[0]["level"] == "medium"
        assert alerts[0]["signal"] == "LOCKUP_IMMINENT"
        assert alerts[0]["days_until"] == 2

    def test_get_alerts_multiple(self, scanner):
        """测试获取多个告警."""
        result = ScanResult()
        result.reports = [
            {
                "ticker": "STRONG",
                "overall_signal": "STRONG_OPPORTUNITY",
                "windows": {"lockup_days_until": 1},
            }
        ]
        
        alerts = scanner.get_alerts(result)
        
        # 应该有强烈机会和禁售期两个告警
        assert len(alerts) == 2
        levels = [a["level"] for a in alerts]
        assert "high" in levels
        assert "medium" in levels

    def test_get_alerts_no_alerts(self, scanner):
        """测试无告警情况."""
        result = ScanResult()
        result.reports = [
            {
                "ticker": "NORMAL",
                "overall_signal": "NO_ACTION",
                "windows": {"lockup_days_until": 30},
            }
        ]
        
        alerts = scanner.get_alerts(result)
        
        assert len(alerts) == 0
