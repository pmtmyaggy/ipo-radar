"""综合评分模块测试."""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.scorer.composite import SignalAggregator, CompositeScorer
from src.scorer.composite import ScoreBreakdown as LocalScoreBreakdown
from src.crawler.models.schemas import (
    OverallSignal,
    CompositeReport,
    WindowsStatus,
    FirstDayPullbackWindow,
    IPOBaseBreakoutWindow,
    LockupExpiryWindow,
    FirstEarningsWindow,
    SentimentResult,
    LockupStatus,
)


class TestScoreBreakdown:
    """测试评分明细类."""

    def test_total_score_calculation(self):
        """测试总分计算."""
        breakdown = LocalScoreBreakdown(
            ticker="TEST",
            fundamental_score=80.0,
            pattern_score=70.0,
            sentiment_score=60.0,
            lockup_risk=20.0,
            earnings_score=75.0,
        )
        
        # 权重: fundamental 0.30, pattern 0.20, sentiment 0.15, lockup 0.15, earnings 0.20
        expected = (
            80.0 * 0.30 +      # 24.0
            70.0 * 0.20 +      # 14.0
            60.0 * 0.15 +      # 9.0
            (100 - 20.0) * 0.15 +  # 12.0
            75.0 * 0.20        # 15.0
        )  # = 74.0
        
        assert breakdown.total_score == pytest.approx(expected)

    def test_total_score_with_zeros(self):
        """测试全零评分."""
        breakdown = LocalScoreBreakdown(ticker="TEST")
        # lockup_risk=0 意味着 (100-0)*0.15 = 15
        expected = 100 * 0.15  # 只有 lockup 贡献
        assert breakdown.total_score == pytest.approx(expected)

    def test_total_score_with_max_values(self):
        """测试满分情况."""
        breakdown = LocalScoreBreakdown(
            ticker="TEST",
            fundamental_score=100.0,
            pattern_score=100.0,
            sentiment_score=100.0,
            lockup_risk=0.0,  # 无风险
            earnings_score=100.0,
        )
        assert breakdown.total_score == pytest.approx(100.0)


class TestSignalAggregator:
    """测试信号聚合器."""

    @pytest.fixture
    def mock_crawler(self):
        """创建模拟crawler."""
        return Mock()

    @pytest.fixture
    def aggregator(self, mock_crawler):
        """创建信号聚合器实例."""
        with patch('src.scorer.composite.IPORadar') as mock_radar, \
             patch('src.scorer.composite.FundamentalScreener') as mock_screener, \
             patch('src.scorer.composite.PatternRecognizer') as mock_pattern, \
             patch('src.scorer.composite.LockupTracker') as mock_lockup, \
             patch('src.scorer.composite.SentimentAnalyzer') as mock_sentiment, \
             patch('src.scorer.composite.EarningsTracker') as mock_earnings:
            agg = SignalAggregator(crawler=mock_crawler)
            return agg

    def test_determine_overall_signal_strong_opportunity(self, aggregator):
        """测试强烈机会信号判定."""
        windows = WindowsStatus()
        windows.ipo_base_breakout.breakout_signal = "strong"
        
        sentiment = SentimentResult(ticker="TEST", overall_score=0.5)
        
        signal, reasons = aggregator._determine_overall_signal(
            windows, fundamental_score=65, sentiment=sentiment
        )
        
        assert signal == OverallSignal.STRONG_OPPORTUNITY
        assert "IPO底部强势突破确认" in reasons

    def test_determine_overall_signal_opportunity(self, aggregator):
        """测试有机会信号判定."""
        windows = WindowsStatus()
        windows.ipo_base_breakout.breakout_signal = "moderate"
        
        sentiment = SentimentResult(ticker="TEST", overall_score=0.0)
        
        signal, reasons = aggregator._determine_overall_signal(
            windows, fundamental_score=55, sentiment=sentiment
        )
        
        assert signal == OverallSignal.OPPORTUNITY
        assert "IPO底部突破信号" in reasons

    def test_determine_overall_signal_watch_base_forming(self, aggregator):
        """测试观察信号 - 底部形成中."""
        windows = WindowsStatus()
        windows.ipo_base_breakout.base_detected = True
        windows.ipo_base_breakout.breakout_signal = None
        
        sentiment = SentimentResult(ticker="TEST", overall_score=0.0)
        
        signal, reasons = aggregator._determine_overall_signal(
            windows, fundamental_score=40, sentiment=sentiment
        )
        
        assert signal == OverallSignal.WATCH
        assert "底部形成中，等待突破" in reasons

    def test_determine_overall_signal_watch_lockup_warning(self, aggregator):
        """测试观察信号 - 禁售期警告."""
        windows = WindowsStatus()
        windows.lockup_expiry.days_until = 10
        
        sentiment = SentimentResult(ticker="TEST", overall_score=0.0)
        
        signal, reasons = aggregator._determine_overall_signal(
            windows, fundamental_score=40, sentiment=sentiment
        )
        
        assert signal == OverallSignal.WATCH
        assert "禁售期10天后到期" in reasons

    def test_determine_overall_signal_no_action(self, aggregator):
        """测试无行动信号."""
        windows = WindowsStatus()
        
        sentiment = SentimentResult(ticker="TEST", overall_score=0.0)
        
        signal, reasons = aggregator._determine_overall_signal(
            windows, fundamental_score=40, sentiment=sentiment
        )
        
        assert signal == OverallSignal.NO_ACTION

    def test_determine_overall_signal_strong_requires_sentiment(self, aggregator):
        """测试强烈机会需要情绪分数达标."""
        windows = WindowsStatus()
        windows.ipo_base_breakout.breakout_signal = "strong"
        
        # 情绪分数不足
        sentiment = SentimentResult(ticker="TEST", overall_score=0.1)
        
        signal, _ = aggregator._determine_overall_signal(
            windows, fundamental_score=65, sentiment=sentiment
        )
        
        # 不满足强烈机会条件，降级为 NO_ACTION (因为 sentiment < 0.3)
        assert signal == OverallSignal.NO_ACTION

    def test_identify_risk_factors_fundamental(self, aggregator):
        """测试识别基本面风险."""
        windows = WindowsStatus()
        
        risks = aggregator._identify_risk_factors(windows, fundamental_score=30)
        
        assert "基本面评分较低" in risks

    def test_identify_risk_factors_lockup(self, aggregator):
        """测试识别禁售期风险."""
        windows = WindowsStatus()
        windows.lockup_expiry.status = LockupStatus.WARNING
        windows.lockup_expiry.supply_impact_pct = 0.25
        
        risks = aggregator._identify_risk_factors(windows, fundamental_score=70)
        
        assert any("禁售期即将到期" in r for r in risks)
        assert any("25.0%" in r for r in risks)

    def test_identify_risk_factors_first_day(self, aggregator):
        """测试识别首日表现风险."""
        windows = WindowsStatus()
        windows.first_day_pullback.signal = "pullback"
        
        risks = aggregator._identify_risk_factors(windows, fundamental_score=70)
        
        assert any("IPO首日表现不佳" in r for r in risks)

    def test_identify_risk_factors_earnings(self, aggregator):
        """测试识别财报风险."""
        windows = WindowsStatus()
        windows.first_earnings.days_until = 5
        
        risks = aggregator._identify_risk_factors(windows, fundamental_score=70)
        
        assert any("首次财报即将发布" in r for r in risks)

    def test_calculate_days_since_ipo(self, aggregator):
        """测试计算上市天数."""
        ipo_info = {"ipo_date": date.today() - timedelta(days=30)}
        
        days = aggregator._calculate_days_since_ipo(ipo_info)
        
        assert days == 30

    def test_calculate_days_since_ipo_none(self, aggregator):
        """测试无IPO信息时返回None."""
        days = aggregator._calculate_days_since_ipo(None)
        assert days is None

    def test_evaluate_first_day_pullback_active(self, aggregator):
        """测试首日回调窗口活跃."""
        ipo_info = {
            "ipo_date": date.today() - timedelta(days=3),
            "ipo_price": 20.0,
        }
        aggregator.crawler.get_latest_price.return_value = 18.0
        
        window = aggregator._evaluate_first_day_pullback("TEST", ipo_info)
        
        assert window.active is True
        assert window.signal == "pullback"

    def test_evaluate_first_day_pullback_inactive(self, aggregator):
        """测试首日回调窗口不活跃（超过5天）."""
        ipo_info = {
            "ipo_date": date.today() - timedelta(days=10),
        }
        
        window = aggregator._evaluate_first_day_pullback("TEST", ipo_info)
        
        assert window.active is False

    def test_evaluate_lockup_expiry(self, aggregator):
        """测试禁售期窗口评估."""
        mock_lockup = Mock()
        mock_lockup.lockup_expiry_date = date.today() + timedelta(days=10)
        mock_lockup.supply_impact_pct = 0.15
        aggregator.lockup.get_lockup_info.return_value = mock_lockup
        
        window = aggregator._evaluate_lockup_expiry("TEST")
        
        assert window.active is True
        assert window.days_until == 10
        assert window.status == LockupStatus.WARNING

    def test_evaluate_lockup_expiry_expired(self, aggregator):
        """测试已过期禁售期."""
        mock_lockup = Mock()
        mock_lockup.lockup_expiry_date = date.today() - timedelta(days=5)
        aggregator.lockup.get_lockup_info.return_value = mock_lockup
        
        window = aggregator._evaluate_lockup_expiry("TEST")
        
        assert window.status == LockupStatus.EXPIRED

    def test_generate_report_error_handling(self, aggregator):
        """测试报告生成错误处理."""
        # 模拟所有方法都失败
        aggregator._get_ipo_info = Mock(return_value=None)
        aggregator.crawler.get_latest_price.side_effect = Exception("API Error")
        
        report = aggregator.generate_report("TEST")
        
        assert report.ticker == "TEST"
        assert report.overall_signal == OverallSignal.NO_ACTION


class TestCompositeScorer:
    """测试综合评分器."""

    def test_score_calculation(self):
        """测试评分计算."""
        # 创建带有 screener 和 sentiment 属性的 mock
        mock_aggregator = Mock()
        
        mock_score = Mock()
        mock_score.total = 75.0
        mock_aggregator.screener = Mock()
        mock_aggregator.screener.score_ipo.return_value = mock_score
        
        mock_aggregator.sentiment = Mock()
        mock_aggregator.sentiment.analyze.return_value = {"score": 0.3, "buzz": "medium"}
        
        mock_report = Mock()
        mock_report.windows.ipo_base_breakout.breakout_signal = "strong"
        mock_report.windows.ipo_base_breakout.base_detected = True
        mock_aggregator.generate_report.return_value = mock_report
        
        scorer = CompositeScorer(mock_aggregator)
        breakdown = scorer.score("TEST")
        
        assert breakdown.ticker == "TEST"
        assert breakdown.fundamental_score == 75.0
        assert breakdown.pattern_score == 90.0  # strong signal

    def test_score_pattern_moderate(self):
        """测试中等突破信号评分."""
        mock_aggregator = Mock()
        mock_aggregator.screener = Mock()
        mock_aggregator.screener.score_ipo.return_value = Mock(total=75.0)
        mock_aggregator.sentiment = Mock()
        mock_aggregator.sentiment.analyze.return_value = {"score": 0.3}
        
        mock_report = Mock()
        mock_report.windows.ipo_base_breakout.breakout_signal = "moderate"
        mock_report.windows.ipo_base_breakout.base_detected = True
        mock_aggregator.generate_report.return_value = mock_report
        
        scorer = CompositeScorer(mock_aggregator)
        breakdown = scorer.score("TEST")
        
        assert breakdown.pattern_score == 70.0

    def test_score_pattern_base_only(self):
        """测试仅有底部检测评分."""
        mock_aggregator = Mock()
        mock_aggregator.screener = Mock()
        mock_aggregator.screener.score_ipo.return_value = Mock(total=75.0)
        mock_aggregator.sentiment = Mock()
        mock_aggregator.sentiment.analyze.return_value = {"score": 0.3}
        
        mock_report = Mock()
        mock_report.windows.ipo_base_breakout.breakout_signal = None
        mock_report.windows.ipo_base_breakout.base_detected = True
        mock_aggregator.generate_report.return_value = mock_report
        
        scorer = CompositeScorer(mock_aggregator)
        breakdown = scorer.score("TEST")
        
        assert breakdown.pattern_score == 50.0

    def test_rank(self):
        """测试排名功能."""
        mock_aggregator = Mock()
        mock_aggregator.screener = Mock()
        mock_aggregator.screener.score_ipo.return_value = Mock(total=75.0)
        mock_aggregator.sentiment = Mock()
        mock_aggregator.sentiment.analyze.return_value = {"score": 0.3}
        
        mock_report = Mock()
        mock_report.windows.ipo_base_breakout.breakout_signal = "strong"
        mock_report.windows.ipo_base_breakout.base_detected = True
        mock_aggregator.generate_report.return_value = mock_report
        
        scorer = CompositeScorer(mock_aggregator)
        results = scorer.rank(["A", "B", "C"])
        
        assert len(results) == 3
        # 所有分数相同，保持原始顺序或按总分排序
        assert all(r.ticker in ["A", "B", "C"] for r in results)
