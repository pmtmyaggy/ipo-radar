"""禁售期追踪模块测试."""

import pytest
from src.lockup.tracker import LockupTracker


class TestLockupTracker:
    """测试禁售期追踪器."""

    def test_tracker_creation(self):
        """测试追踪器创建."""
        tracker = LockupTracker()
        assert tracker is not None
        assert hasattr(tracker, 'crawler')

    def test_get_lockup_info_method(self):
        """测试方法存在."""
        tracker = LockupTracker()
        assert hasattr(tracker, 'get_lockup_info')
