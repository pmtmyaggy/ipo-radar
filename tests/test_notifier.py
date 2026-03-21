"""通知模块测试."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.notifier import FeishuNotifier, NotificationManager


class TestFeishuNotifier:
    """测试飞书通知器."""

    @pytest.fixture
    def notifier(self):
        """创建通知器实例."""
        return FeishuNotifier(webhook_url="https://test.webhook.url")

    @pytest.fixture
    def mock_report(self):
        """创建模拟报告."""
        return {
            "ticker": "TEST",
            "company_name": "Test Company",
            "current_price": 100.0,
            "price_vs_ipo": 1.25,
            "fundamental_score": 75,
            "overall_signal": "STRONG_OPPORTUNITY",
            "signal_reasons": ["Strong breakout", "Good fundamentals"],
            "risk_factors": ["Lockup expiry soon"],
            "windows": {},
        }

    def test_init_with_url(self):
        """测试使用URL初始化."""
        notifier = FeishuNotifier("https://test.url")
        assert notifier.webhook_url == "https://test.url"
        assert notifier.enabled is True

    def test_init_from_env(self):
        """测试从环境变量初始化."""
        with patch.dict('os.environ', {'FEISHU_WEBHOOK_URL': 'https://env.url'}):
            notifier = FeishuNotifier()
            assert notifier.webhook_url == "https://env.url"
            assert notifier.enabled is True

    def test_init_no_url(self):
        """测试无URL初始化."""
        with patch.dict('os.environ', {}, clear=True):
            notifier = FeishuNotifier()
            assert notifier.webhook_url is None
            assert notifier.enabled is False

    @patch('requests.post')
    def test_send_message_success(self, mock_post, notifier):
        """测试发送消息成功."""
        mock_post.return_value = Mock(
            status_code=200, 
            json=lambda: {"code": 0},
            raise_for_status=lambda: None
        )
        
        result = notifier.send_message("Test Title", "Test content")
        
        assert result is True
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_send_message_failure(self, mock_post, notifier):
        """测试发送消息失败."""
        mock_post.return_value = Mock(
            status_code=500, 
            text="Error",
            raise_for_status=lambda: None,
            json=lambda: {"code": 1, "msg": "error"}
        )
        
        result = notifier.send_message("Test Title", "Test content")
        
        assert result is False

    def test_send_message_disabled(self, notifier):
        """测试通知器禁用时发送消息."""
        notifier.enabled = False
        result = notifier.send_message("Test Title", "Test content")
        assert result is False

    @patch('requests.post')
    def test_send_strong_opportunity_alert(self, mock_post, notifier, mock_report):
        """测试强烈机会告警."""
        mock_post.return_value = Mock(
            status_code=200, 
            json=lambda: {"code": 0},
            raise_for_status=lambda: None
        )
        
        result = notifier.send_strong_opportunity_alert(mock_report)
        
        assert result is True
        call_args = mock_post.call_args
        assert "TEST" in str(call_args)

    @patch('requests.post')
    def test_send_breakout_alert(self, mock_post, notifier):
        """测试突破信号告警."""
        mock_post.return_value = Mock(
            status_code=200, 
            json=lambda: {"code": 0},
            raise_for_status=lambda: None
        )
        
        report = {
            "ticker": "ABC",
            "current_price": 150.0,
            "windows": {"breakout_signal": "strong"},
        }
        result = notifier.send_breakout_alert(report)
        
        assert result is True

    @patch('requests.post')
    def test_send_lockup_warning(self, mock_post, notifier):
        """测试禁售期警告."""
        mock_post.return_value = Mock(
            status_code=200, 
            json=lambda: {"code": 0},
            raise_for_status=lambda: None
        )
        
        result = notifier.send_lockup_warning("XYZ", 3, 0.25)
        
        assert result is True
        call_args = str(mock_post.call_args)
        assert "3" in call_args

    @patch('requests.post')
    def test_send_earnings_reminder(self, mock_post, notifier):
        """测试财报提醒."""
        mock_post.return_value = Mock(
            status_code=200, 
            json=lambda: {"code": 0},
            raise_for_status=lambda: None
        )
        
        result = notifier.send_earnings_reminder("TEST", 5)
        
        assert result is True

    @patch('requests.post')
    def test_send_daily_summary(self, mock_post, notifier):
        """测试每日摘要."""
        mock_post.return_value = Mock(
            status_code=200, 
            json=lambda: {"code": 0},
            raise_for_status=lambda: None
        )
        
        mock_result = Mock()
        mock_result.total_count = 10
        mock_result.strong_opportunity_count = 2
        mock_result.opportunity_count = 3
        mock_result.watch_count = 4
        mock_result.no_action_count = 1
        mock_result.scanned_at = datetime.now()
        mock_result.reports = []
        mock_result.errors = []
        
        result = notifier.send_daily_summary(mock_result)
        
        assert result is True


class TestNotificationManager:
    """测试通知管理器."""

    @pytest.fixture
    def mock_notifier(self):
        """创建模拟通知器."""
        mock = Mock(spec=FeishuNotifier)
        mock.enabled = True
        return mock

    @pytest.fixture
    def manager(self, mock_notifier):
        """创建通知管理器实例."""
        return NotificationManager(notifier=mock_notifier)

    def test_process_scan_result(self, manager, mock_notifier):
        """测试处理扫描结果."""
        mock_result = Mock()
        mock_result.scanned_at = datetime.now()
        mock_result.total_count = 5
        mock_result.strong_opportunity_count = 1
        mock_result.opportunity_count = 2
        mock_result.watch_count = 1
        mock_result.no_action_count = 1
        mock_result.reports = [
            {
                "ticker": "STRONG",
                "overall_signal": "STRONG_OPPORTUNITY",
                "signal_reasons": ["Breakout"],
                "windows": {"lockup_days_until": 2, "supply_impact_pct": 0.2},
            },
            {
                "ticker": "NORMAL",
                "overall_signal": "OPPORTUNITY",
                "windows": {},
            },
        ]
        mock_result.errors = []
        
        manager.process_scan_result(mock_result)
        
        # 应该发送每日摘要
        mock_notifier.send_daily_summary.assert_called_once_with(mock_result)
        
        # 应该发送强烈机会告警
        mock_notifier.send_strong_opportunity_alert.assert_called_once()
        
        # 应该发送禁售期警告（因为lockup_days_until=2 <= 3）
        mock_notifier.send_lockup_warning.assert_called_once_with("STRONG", 2, 0.2)

    def test_process_scan_result_disabled(self, manager, mock_notifier):
        """测试通知器禁用时处理扫描结果."""
        mock_notifier.enabled = False
        mock_result = Mock()
        
        manager.process_scan_result(mock_result)
        
        # 不应该发送任何通知
        mock_notifier.send_daily_summary.assert_not_called()
