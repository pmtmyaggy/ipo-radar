"""监控系统测试.

测试PRD 6.2监控告警功能。
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.monitoring.monitor import CrawlerMonitor, CrawlerMetrics, MonitorMetrics, monitored
from src.monitoring.alerter import FeishuAlerter, AlertManager


class TestCrawlerMetrics:
    """测试爬虫指标."""

    def test_success_rate_calculation(self):
        """测试成功率计算."""
        metrics = CrawlerMetrics(
            crawler_name="test",
            total_requests=100,
            successful_requests=80,
            failed_requests=20,
        )
        
        assert metrics.success_rate == 0.8
    
    def test_avg_response_time(self):
        """测试平均响应时间."""
        metrics = CrawlerMetrics(
            crawler_name="test",
            total_requests=10,
            total_response_time_ms=5000.0,
        )
        
        assert metrics.avg_response_time_ms == 500.0
    
    def test_is_healthy(self):
        """测试健康状态."""
        # 最近成功过 - 健康
        metrics = CrawlerMetrics(
            crawler_name="test",
            last_success_time=datetime.now(),
        )
        assert metrics.is_healthy is True
        
        # 超过2小时未成功 - 不健康
        metrics = CrawlerMetrics(
            crawler_name="test",
            last_success_time=datetime.now() - timedelta(hours=3),
        )
        assert metrics.is_healthy is False
        
        # 从未成功 - 不健康
        metrics = CrawlerMetrics(crawler_name="test")
        assert metrics.is_healthy is False


class TestCrawlerMonitor:
    """测试爬虫监控器."""

    def test_record_success(self):
        """测试记录成功请求."""
        monitor = CrawlerMonitor()
        
        monitor.record_success("ipo_calendar", 150.0)
        
        metrics = monitor.get_metrics("ipo_calendar")
        assert metrics.crawler_metrics["ipo_calendar"].successful_requests == 1
        assert metrics.crawler_metrics["ipo_calendar"].total_requests == 1
    
    def test_record_failure(self):
        """测试记录失败请求."""
        monitor = CrawlerMonitor()
        
        monitor.record_failure("ipo_calendar", 50.0)
        
        metrics = monitor.get_metrics("ipo_calendar")
        assert metrics.crawler_metrics["ipo_calendar"].failed_requests == 1
        assert metrics.crawler_metrics["ipo_calendar"].total_requests == 1
    
    def test_check_health(self):
        """测试健康检查."""
        monitor = CrawlerMonitor()
        
        # 记录一个健康的爬虫
        monitor.record_success("healthy_crawler", 100.0)
        
        # 记录一个不健康的爬虫（模拟历史记录）
        monitor._metrics["unhealthy_crawler"].last_success_time = (
            datetime.now() - timedelta(hours=3)
        )
        
        issues = monitor.check_health()
        
        assert "healthy_crawler" not in issues['unhealthy_crawlers']
        assert "unhealthy_crawler" in issues['unhealthy_crawlers']
    
    def test_should_alert(self):
        """测试告警冷却."""
        monitor = CrawlerMonitor()
        
        # 第一次应该告警
        assert monitor.should_alert("test_alert", cooldown_minutes=60) is True
        
        # 立即再次检查，不应该告警（冷却期内）
        assert monitor.should_alert("test_alert", cooldown_minutes=60) is False
    
    def test_generate_report(self):
        """测试生成报告."""
        monitor = CrawlerMonitor()
        
        monitor.record_success("ipo_calendar", 200.0)
        
        report = monitor.generate_report()
        
        assert "监控报告" in report
        assert "ipo_calendar" in report
        assert "成功率" in report


class TestFeishuAlerter:
    """测试飞书告警器."""

    def test_init_without_webhook(self):
        """测试无webhook初始化."""
        alerter = FeishuAlerter(webhook_url=None)
        assert alerter.enabled is False
    
    def test_init_with_webhook(self):
        """测试有webhook初始化."""
        alerter = FeishuAlerter(webhook_url="https://test.webhook.url")
        assert alerter.enabled is True
    
    @patch('requests.post')
    def test_send_alert_disabled(self, mock_post):
        """测试禁用状态发送."""
        alerter = FeishuAlerter(webhook_url=None)
        
        result = alerter.send_alert("Test", "Content")
        
        assert result is False
        mock_post.assert_not_called()
    
    @patch('requests.post')
    def test_send_alert_success(self, mock_post):
        """测试成功发送."""
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"code": 0},
        )
        
        alerter = FeishuAlerter(webhook_url="https://test.webhook.url")
        result = alerter.send_alert("Test", "Content")
        
        assert result is True
        mock_post.assert_called_once()


class TestAlertManager:
    """测试告警管理器."""

    def test_check_and_alert_no_issues(self):
        """测试无问题时不会告警."""
        monitor = Mock()
        monitor.check_health.return_value = {
            'unhealthy_crawlers': [],
            'stale_tables': [],
        }
        
        alerter = Mock()
        
        manager = AlertManager(monitor=monitor, alerter=alerter)
        result = manager.check_and_alert()
        
        assert result is False
        alerter.send_alert.assert_not_called()

    def test_send_daily_summary(self):
        """测试发送每日摘要."""
        monitor = Mock()
        monitor.generate_report.return_value = "Test report"
        
        alerter = Mock()
        alerter.send_alert.return_value = True
        
        manager = AlertManager(monitor=monitor, alerter=alerter)
        result = manager.send_daily_summary()
        
        assert result is True
        alerter.send_alert.assert_called_once()


class TestMonitoredDecorator:
    """测试监控装饰器."""

    def test_decorator_records_success(self):
        """测试装饰器记录成功."""
        
        @monitored("test_crawler")
        def successful_function():
            return "success"
        
        result = successful_function()
        
        assert result == "success"
    
    def test_decorator_records_failure(self):
        """测试装饰器记录失败."""
        
        @monitored("test_crawler")
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_function()


class TestMonitoringIntegration:
    """监控集成测试."""

    def test_end_to_end_monitoring(self):
        """测试端到端监控流程."""
        # 1. 创建监控器
        monitor = CrawlerMonitor()
        
        # 2. 模拟请求
        for _ in range(10):
            monitor.record_success("ipo_calendar", 150.0)
        
        for _ in range(2):
            monitor.record_failure("ipo_calendar", 50.0)
        
        # 3. 获取指标
        metrics = monitor.get_metrics()
        
        assert "ipo_calendar" in metrics.crawler_metrics
        assert metrics.crawler_metrics["ipo_calendar"].success_rate == 10/12
        
        # 4. 健康检查
        issues = monitor.check_health()
        # 刚记录的成功，应该是健康的
        assert "ipo_calendar" not in issues['unhealthy_crawlers']
