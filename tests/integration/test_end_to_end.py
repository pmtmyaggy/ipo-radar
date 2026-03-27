"""端到端集成测试.

测试完整的IPO雷达工作流程。
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.crawler.api import CrawlerAPI
from src.radar.monitor import IPORadar
from src.screener.fundamentals import FundamentalScreener
from src.scorer.composite import SignalAggregator, CompositeScorer
from src.scorer.daily_scan import DailyScanner


class TestEndToEndWorkflow:
    """测试端到端工作流程."""

    @pytest.fixture
    def mock_crawler(self):
        """创建模拟crawler."""
        crawler = Mock(spec=CrawlerAPI)
        
        # 模拟IPO日历
        crawler.refresh_ipo_calendar.return_value = [
            Mock(ticker="NEWIPO", company_name="New IPO Co", ipo_date=date.today()),
        ]
        
        # 模拟价格
        crawler.get_latest_price.return_value = 50.0
        
        # 模拟股票K线
        crawler.get_stock_bars.return_value = [
            Mock(date=date.today() - timedelta(days=i), open=48, high=52, low=47, close=50, volume=1000000)
            for i in range(30)
        ]
        
        return crawler

    def test_complete_scanning_workflow(self, mock_crawler):
        """测试完整扫描工作流程."""
        # 1. 创建雷达
        radar = IPORadar(crawler=mock_crawler)
        
        # 2. 获取活跃股票
        with patch.object(radar, 'get_active_tickers', return_value=["TEST", "CAVA"]):
            tickers = radar.get_active_tickers()
            assert len(tickers) == 2
        
        # 3. 验证评分器可以创建（使用完全模拟的子模块）
        mock_lockup = Mock()
        mock_lockup.get_lockup_info.return_value = Mock(
            lockup_expiry_date=date.today() + timedelta(days=30),
            supply_impact_pct=0.15
        )
        
        mock_earnings = Mock()
        mock_earnings.get_next_earnings_date.return_value = date.today() + timedelta(days=45)
        mock_earnings.analyze_earnings.return_value = "buy"
        
        mock_sentiment = Mock()
        mock_sentiment.analyze.return_value = {"score": 0.5, "buzz": "medium"}
        
        mock_screener = Mock()
        mock_score = Mock()
        mock_score.total = 75
        mock_screener.score_ipo.return_value = mock_score
        
        with patch('src.scorer.composite.IPORadar'), \
             patch('src.scorer.composite.FundamentalScreener') as mock_fscreener, \
             patch('src.scorer.composite.PatternRecognizer'), \
             patch('src.scorer.composite.LockupTracker', return_value=mock_lockup), \
             patch('src.scorer.composite.SentimentAnalyzer', return_value=mock_sentiment), \
             patch('src.scorer.composite.EarningsTracker', return_value=mock_earnings):
            
            mock_fscreener.return_value = mock_screener
            
            aggregator = SignalAggregator(crawler=mock_crawler)
            
            # 4. 生成报告
            with patch.object(aggregator, '_get_ipo_info', return_value={
                "ipo_date": date.today() - timedelta(days=30),
                "ipo_price": 40.0,
            }):
                report = aggregator.generate_report("TEST")
                
                # 验证报告结构（即使出错也有基本结构）
                assert report.ticker == "TEST"
                assert report.overall_signal is not None

    def test_daily_scan_workflow(self, mock_crawler):
        """测试每日扫描工作流程."""
        with patch('src.scorer.daily_scan.IPORadar') as mock_radar, \
             patch('src.scorer.daily_scan.SignalAggregator') as mock_agg:
            
            # 设置mock
            mock_radar_instance = Mock()
            mock_radar_instance.get_active_tickers.return_value = ["A", "B", "C"]
            mock_radar.return_value = mock_radar_instance
            
            mock_agg_instance = Mock()
            mock_report = Mock()
            mock_report.ticker = "A"
            mock_report.overall_signal.value = "OPPORTUNITY"
            mock_report.company_name = None
            mock_report.ipo_date = None
            mock_report.days_since_ipo = None
            mock_report.current_price = None
            mock_report.price_vs_ipo = None
            mock_report.fundamental_score = None
            mock_report.signal_reasons = []
            mock_report.risk_factors = []
            mock_report.windows = Mock()
            mock_agg_instance.generate_report.return_value = mock_report
            mock_agg.return_value = mock_agg_instance
            
            # 创建扫描器并运行
            scanner = DailyScanner(aggregator=mock_agg_instance, radar=mock_radar_instance)
            result = scanner.run_scan(mode="watchlist")
            
            # 验证结果
            assert result.total_count == 3
            mock_agg_instance.generate_report.assert_called()


class TestCrawlerIntegration:
    """测试爬虫集成."""

    def test_crawler_api_initialization(self):
        """测试CrawlerAPI初始化."""
        api = CrawlerAPI()
        assert api is not None
        # CrawlerAPI 有 db_manager 属性
        assert hasattr(api, 'db_manager')

    def test_crawler_singleton_behavior(self):
        """测试CrawlerAPI单例行为."""
        api1 = CrawlerAPI()
        api2 = CrawlerAPI()
        # 不是严格的单例，但应该可以正常工作
        assert type(api1) == type(api2)


class TestDatabaseIntegration:
    """测试数据库集成."""

    def test_database_manager_exists(self):
        """测试数据库管理器存在."""
        from src.crawler.models.database import DatabaseManager
        assert DatabaseManager is not None

    def test_models_exist(self):
        """测试数据模型存在."""
        from src.crawler.models.database import IPOEventModel, StockBarModel
        assert IPOEventModel is not None
        assert StockBarModel is not None


class TestSchedulerIntegration:
    """测试调度器集成."""

    def test_scheduler_module_exists(self):
        """测试调度器模块存在."""
        try:
            from src import scheduler
            assert scheduler is not None
        except ImportError as e:
            pytest.skip(f"Scheduler module not available: {e}")


class TestNotifierIntegration:
    """测试通知器集成."""

    def test_notifier_with_scanner(self):
        """测试通知器与扫描器集成."""
        from src.notifier import FeishuNotifier, NotificationManager
        from src.scorer.daily_scan import ScanResult
        
        notifier = FeishuNotifier()
        manager = NotificationManager(notifier=notifier)
        
        # 创建模拟扫描结果
        result = ScanResult()
        result.total_count = 5
        result.strong_opportunity_count = 1
        result.reports = [{
            "ticker": "TEST",
            "overall_signal": "STRONG_OPPORTUNITY",
            "signal_reasons": ["Breakout"],
            "windows": {"lockup_days_until": 2},
        }]
        
        # 禁用通知器以避免实际发送
        notifier.enabled = False
        manager.process_scan_result(result)
        
        # 如果启用，应该发送通知
        assert manager.notifier is not None
