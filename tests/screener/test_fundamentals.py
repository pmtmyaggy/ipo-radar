"""基本面筛选模块测试."""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch

from src.screener.fundamentals import (
    FundamentalScreener,
    ScreenCriteria,
    TOP_TEN_UNDERWRITERS,
)
from src.crawler.models.schemas import QuickScore, S1Metrics


class TestScreenCriteria:
    """测试筛选条件类."""

    def test_default_criteria(self):
        """测试默认条件."""
        criteria = ScreenCriteria()
        assert criteria.min_revenue_growth is None
        assert criteria.min_gross_margin is None

    def test_custom_criteria(self):
        """测试自定义条件."""
        criteria = ScreenCriteria(
            min_revenue_growth=0.20,
            min_gross_margin=0.50,
            min_market_cap=1_000_000_000,
        )
        assert criteria.min_revenue_growth == 0.20
        assert criteria.min_gross_margin == 0.50
        assert criteria.min_market_cap == 1_000_000_000


class TestFundamentalScreener:
    """测试基本面筛选器."""

    @pytest.fixture
    def screener(self):
        """创建筛选器实例."""
        return FundamentalScreener()

    @pytest.fixture
    def perfect_metrics(self):
        """创建完美指标（应得100分）."""
        return S1Metrics(
            revenue_growth=Decimal("0.30"),  # >20% = 25分
            gross_margin=Decimal("0.70"),    # >60% = 20分
            cash_runway_months=Decimal("24"), # >18月 = 20分
            debt_to_assets=Decimal("0.20"),   # <0.3 = 15分
            lead_underwriter="Goldman Sachs", # 前十 = 10分
            market_cap=Decimal("2000000000"), # >$1B = 10分
        )

    @pytest.fixture
    def poor_metrics(self):
        """创建较差指标."""
        return S1Metrics(
            revenue_growth=Decimal("0.05"),   # <10% = 0分
            gross_margin=Decimal("0.30"),     # <40% = 0分
            cash_runway_months=Decimal("6"),  # <12月 = 0分
            debt_to_assets=Decimal("0.80"),   # >0.6 = 0分
            lead_underwriter="Unknown Bank",  # 非前十 = 0分
            market_cap=Decimal("100000000"),  # <$500M = 0分
        )

    def test_calculate_quick_score_perfect(self, screener, perfect_metrics):
        """测试完美评分."""
        score = screener.calculate_quick_score("PERFECT", perfect_metrics)
        
        assert score.total == 100
        assert score.verdict == "PASS"
        assert score.details["revenue"] == 25
        assert score.details["margin"] == 20
        assert score.details["cash"] == 20
        assert score.details["debt"] == 15
        assert score.details["underwriter"] == 10
        assert score.details["market_cap"] == 10

    def test_calculate_quick_score_poor(self, screener, poor_metrics):
        """测试较差评分."""
        score = screener.calculate_quick_score("POOR", poor_metrics)
        
        assert score.total == 0
        assert score.verdict == "FAIL"

    def test_calculate_quick_score_review(self, screener):
        """测试边界评分(REVIEW)."""
        metrics = S1Metrics(
            ticker="REVIEW",
            revenue_growth=Decimal("0.15"),  # 15分
            gross_margin=Decimal("0.50"),    # 12分
            cash_runway_months=Decimal("15"), # 10分
            debt_to_assets=Decimal("0.45"),   # 8分
            lead_underwriter=None,
            market_cap=None,
        )
        score = screener.calculate_quick_score("REVIEW", metrics)
        
        # 总分 = 15 + 12 + 10 + 8 = 45，应该在40-60之间
        assert 40 <= score.total <= 60
        assert score.verdict == "REVIEW"

    def test_calculate_quick_score_missing_data(self, screener):
        """测试缺失数据处理."""
        metrics = S1Metrics()
        score = screener.calculate_quick_score("MISSING", metrics)
        
        # 所有指标为None，应该得0分
        assert score.total == 0
        assert score.verdict == "FAIL"

    def test_calculate_quick_score_partial_data(self, screener):
        """测试部分数据处理."""
        metrics = S1Metrics(
            revenue_growth=Decimal("0.25"),  # 25分
            gross_margin=Decimal("0.65"),    # 20分
        )
        score = screener.calculate_quick_score("PARTIAL", metrics)
        
        # 只有部分指标，总分 = 25 + 20 = 45
        assert score.total == 45
        assert score.verdict == "REVIEW"

    def test_revenue_growth_boundary(self, screener):
        """测试营收增速边界值."""
        # 正好20%
        metrics = S1Metrics(
            revenue_growth=Decimal("0.20"),
        )
        score = screener.calculate_quick_score("BOUNDARY", metrics)
        assert score.details["revenue"] == 15  # 10-20%区间
        
        # 略大于20%
        metrics2 = S1Metrics(revenue_growth=Decimal("0.2001"))
        score = screener.calculate_quick_score("BOUNDARY2", metrics2)
        assert score.details["revenue"] == 25  # >20%

    def test_gross_margin_boundary(self, screener):
        """测试毛利率边界值."""
        # 正好60%
        metrics = S1Metrics(
            gross_margin=Decimal("0.60"),
        )
        score = screener.calculate_quick_score("BOUNDARY", metrics)
        assert score.details["margin"] == 12  # 40-60%区间

    def test_debt_ratio_boundary(self, screener):
        """测试债务比例边界值."""
        # 正好30%
        metrics = S1Metrics(
            debt_to_assets=Decimal("0.30"),
        )
        score = screener.calculate_quick_score("BOUNDARY", metrics)
        assert score.details["debt"] == 8  # 30-60%区间，不是<30%

    def test_market_cap_boundary(self, screener):
        """测试市值边界值."""
        # 正好$1B
        metrics = S1Metrics(
            market_cap=Decimal("1000000000"),
        )
        score = screener.calculate_quick_score("BOUNDARY", metrics)
        assert score.details["market_cap"] == 5  # $500M-1B区间

    def test_top_ten_underwriters_list(self):
        """测试十大承销商列表."""
        assert "Goldman Sachs" in TOP_TEN_UNDERWRITERS
        assert "Morgan Stanley" in TOP_TEN_UNDERWRITERS
        assert len(TOP_TEN_UNDERWRITERS) == 10

    def test_underwriter_matching(self, screener):
        """测试承销商匹配."""
        # 完整名称
        metrics = S1Metrics(
            lead_underwriter="Goldman Sachs",
        )
        score = screener.calculate_quick_score("TEST", metrics)
        assert score.details["underwriter"] == 10
        
        # 部分匹配
        metrics2 = S1Metrics(lead_underwriter="Goldman Sachs & Co.")
        score = screener.calculate_quick_score("TEST2", metrics2)
        assert score.details["underwriter"] == 10

    def test_batch_score(self, screener):
        """测试批量评分."""
        with patch.object(screener, 'score_ipo') as mock_score:
            mock_score.side_effect = [
                QuickScore(ticker="A", total=80, verdict="PASS"),
                QuickScore(ticker="B", total=50, verdict="REVIEW"),
                QuickScore(ticker="C", total=30, verdict="FAIL"),
            ]
            
            results = screener.batch_score(["A", "B", "C"])
            
            assert len(results) == 3
            # 应该按分数排序
            assert results[0].total >= results[1].total >= results[2].total

    def test_screen_with_criteria(self, screener):
        """测试带条件的筛选."""
        with patch.object(screener, 'score_ipo') as mock_score:
            mock_score.side_effect = [
                QuickScore(ticker="A", total=80, verdict="PASS"),
                QuickScore(ticker="B", total=50, verdict="REVIEW"),
                QuickScore(ticker="C", total=30, verdict="FAIL"),
            ]
            
            criteria = ScreenCriteria()
            results = screener.screen(["A", "B", "C"], criteria)
            
            # 默认应该只返回PASS
            assert "A" in results
            assert "B" not in results
            assert "C" not in results

    def test_screen_default_behavior(self, screener):
        """测试默认筛选行为."""
        with patch.object(screener, 'score_ipo') as mock_score:
            mock_score.side_effect = [
                QuickScore(ticker="A", total=80, verdict="PASS"),
                QuickScore(ticker="B", total=50, verdict="REVIEW"),
                QuickScore(ticker="C", total=30, verdict="FAIL"),
            ]
            
            results = screener.screen(["A", "B", "C"])
            
            # PASS和REVIEW都应该被包含
            assert "A" in results
            assert "B" in results
            assert "C" not in results

    def test_score_ipo_no_data(self, screener):
        """测试无数据时的评分."""
        with patch.object(screener, '_get_s1_metrics', return_value=None):
            score = screener.score_ipo("NODATA")
            
            assert score.total == 0
            assert score.verdict == "FAIL"
            # 无数据时details为空
            assert score.details == {}


class TestS1Metrics:
    """测试S1Metrics数据类."""

    def test_s1_metrics_creation(self):
        """测试创建S1Metrics."""
        metrics = S1Metrics(
            revenue_growth=Decimal("0.25"),
            gross_margin=Decimal("0.60"),
        )
        
        assert metrics.revenue_growth == Decimal("0.25")
        assert metrics.gross_margin == Decimal("0.60")

    def test_s1_metrics_defaults(self):
        """测试S1Metrics默认值."""
        metrics = S1Metrics()
        
        assert metrics.revenue_growth is None
        assert metrics.gross_margin is None
        assert metrics.cash_runway_months is None
