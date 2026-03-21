"""测试数据模型."""

import pytest
from decimal import Decimal
from datetime import date, datetime

from src.crawler.models.schemas import (
    IPOEvent,
    StockBar,
    NewsItem,
    LockupInfo,
    QuickScore,
    IPOStatus,
    LockupStatus,
)


class TestIPOEvent:
    """测试IPO事件模型."""
    
    def test_create_ipo_event(self, sample_ipo_event):
        """测试创建IPO事件."""
        event = IPOEvent(**sample_ipo_event)
        
        assert event.ticker == "TEST"
        assert event.company_name == "Test Company Inc."
        assert event.status == IPOStatus.TRADING
        assert event.price_range_low == Decimal("15.0")
    
    def test_ticker_uppercase(self):
        """测试股票代码自动转为大写."""
        event = IPOEvent(
            ticker="test",
            company_name="Test",
            status=IPOStatus.FILED,
        )
        assert event.ticker == "TEST"
    
    def test_optional_fields(self):
        """测试可选字段."""
        event = IPOEvent(
            company_name="Minimal Company",
            status=IPOStatus.FILED,
        )
        
        assert event.ticker is None
        assert event.cik is None
        assert event.final_price is None


class TestStockBar:
    """测试行情数据模型."""
    
    def test_create_stock_bar(self):
        """测试创建行情数据."""
        bar = StockBar(
            ticker="AAPL",
            date=date(2024, 1, 15),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.50"),
            close=Decimal("153.00"),
            volume=1000000,
        )
        
        assert bar.ticker == "AAPL"
        assert bar.close == Decimal("153.00")
    
    def test_vwap_optional(self):
        """测试VWAP可选."""
        bar = StockBar(
            ticker="AAPL",
            date=date(2024, 1, 15),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.50"),
            close=Decimal("153.00"),
            volume=1000000,
            vwap=None,
        )
        
        assert bar.vwap is None


class TestLockupInfo:
    """测试禁售期信息模型."""
    
    def test_create_lockup_info(self):
        """测试创建禁售期信息."""
        info = LockupInfo(
            ticker="TEST",
            ipo_date=date(2024, 6, 15),
            lockup_days=180,
            lockup_expiry_date=date(2024, 12, 12),
            shares_locked=5000000,
            locked_holders=["founders", "vc"],
            supply_impact_pct=Decimal("0.25"),
            status=LockupStatus.ACTIVE,
        )
        
        assert info.ticker == "TEST"
        assert info.lockup_days == 180
        assert info.status == LockupStatus.ACTIVE


class TestQuickScore:
    """测试快速评分模型."""
    
    def test_calculate_total(self):
        """测试总分计算."""
        score = QuickScore(
            ticker="TEST",
            total=75,
            details={
                "revenue": 25,
                "margin": 20,
                "cash": 15,
                "debt": 10,
            },
            verdict="PASS",
        )
        
        assert score.total == 75
        assert score.verdict == "PASS"
        assert len(score.details) == 4


class TestEnumValidation:
    """测试枚举类型."""
    
    def test_ipo_status_values(self):
        """测试IPO状态枚举值."""
        assert IPOStatus.FILED.value == "filed"
        assert IPOStatus.PRICED.value == "priced"
        assert IPOStatus.TRADING.value == "trading"
        assert IPOStatus.WITHDRAWN.value == "withdrawn"
    
    def test_lockup_status_values(self):
        """测试禁售期状态枚举值."""
        assert LockupStatus.ACTIVE.value == "active"
        assert LockupStatus.WARNING.value == "warning"
        assert LockupStatus.IMMINENT.value == "imminent"
        assert LockupStatus.EXPIRED.value == "expired"
