"""财报追踪模块测试."""

import pytest
from src.earnings.tracker import EarningsTracker


class TestEarningsTracker:
    """测试财报追踪器."""

    def test_tracker_creation(self):
        """测试追踪器创建."""
        tracker = EarningsTracker()
        assert tracker is not None
        assert hasattr(tracker, 'crawler')

    def test_analyze_earnings(self):
        """测试财报分析方法存在."""
        tracker = EarningsTracker()
        assert hasattr(tracker, 'analyze_earnings')


class TestEarningsCalendar:
    """测试财报日历."""

    def test_calendar_creation(self):
        """测试日历创建."""
        from src.earnings.tracker import EarningsCalendar, EarningsTracker
        tracker = EarningsTracker()
        calendar = EarningsCalendar(tracker)
        assert calendar is not None
