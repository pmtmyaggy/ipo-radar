"""测试EDGAR监控器."""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch

import requests

from src.crawler.edgar_monitor import EdgarMonitor, EdgarObserver, EdgarIPOCrawler


class MockObserver(EdgarObserver):
    """模拟观察者."""
    
    def __init__(self):
        self.s1_calls = []
        self.b4_calls = []
    
    def on_new_s1(self, filing: dict) -> None:
        self.s1_calls.append(filing)
    
    def on_new_424b4(self, filing: dict) -> None:
        self.b4_calls.append(filing)


class TestEdgarMonitor:
    """测试EDGAR监控器."""
    
    @pytest.fixture
    def monitor(self):
        return EdgarMonitor(poll_interval=60)
    
    @pytest.fixture
    def sample_search_response(self):
        """示例EDGAR搜索响应."""
        return {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "ciks": ["0001234567"],
                            "display_names": ["Test Company Inc."],
                            "form": "S-1",
                            "file_date": "2024-01-15",
                            "adsh": "0001234567-24-000001",
                        }
                    }
                ]
            }
        }
    
    def test_initialization(self, monitor):
        """测试初始化."""
        assert monitor.poll_interval == 60
        assert monitor._running is False
        assert len(monitor._observers) == 0
    
    def test_register_observer(self, monitor):
        """测试注册观察者."""
        observer = MockObserver()
        monitor.register_observer(observer)
        
        assert len(monitor._observers) == 1
        assert monitor._observers[0] == observer
    
    def test_unregister_observer(self, monitor):
        """测试注销观察者."""
        observer = MockObserver()
        monitor.register_observer(observer)
        monitor.unregister_observer(observer)
        
        assert len(monitor._observers) == 0
    
    def test_notify_s1(self, monitor):
        """测试通知S-1."""
        observer = MockObserver()
        monitor.register_observer(observer)
        
        test_filing = {"cik": "000123", "form_type": "S-1"}
        monitor._notify_s1(test_filing)
        
        assert len(observer.s1_calls) == 1
        assert observer.s1_calls[0] == test_filing
    
    def test_parse_search_results(self, monitor, sample_search_response):
        """测试解析搜索结果."""
        filings = monitor._parse_search_results(sample_search_response, "S-1")
        
        assert len(filings) == 1
        assert filings[0]["cik"] == "0001234567"
        assert filings[0]["form_type"] == "S-1"
        assert "filing_url" in filings[0]
    
    def test_build_filing_url(self, monitor):
        """测试构建文件URL."""
        source = {
            "ciks": ["1234567"],
            "adsh": "0001234567-24-000001",
        }
        
        url = monitor._build_filing_url(source)
        
        assert "1234567" in url
        assert "000123456724000001" in url
    
    def test_build_filing_url_missing_data(self, monitor):
        """测试构建URL缺少数据."""
        source = {"ciks": [], "adsh": ""}
        url = monitor._build_filing_url(source)
        
        assert url == ""
    
    @patch('src.crawler.edgar_monitor.requests.request')
    def test_search_filings_success(self, mock_request, monitor, sample_search_response):
        """测试成功搜索文件."""
        mock_response = Mock()
        mock_response.json.return_value = sample_search_response
        mock_response.ok = True
        mock_request.return_value = mock_response
        
        filings = monitor._search_filings(
            "S-1",
            date(2024, 1, 1),
            date(2024, 1, 31),
        )
        
        assert len(filings) == 1
    
    def test_search_filings_error(self, monitor):
        """测试搜索错误."""
        from src.crawler.utils.retry import RetryError
        
        # Mock _request 直接抛出异常（模拟重试后失败）
        with patch.object(monitor, '_request', side_effect=RetryError("Failed after retries")):
            filings = monitor._search_filings(
                "S-1",
                date(2024, 1, 1),
                date(2024, 1, 31),
            )
            
            assert len(filings) == 0
    
    def test_poll_triggers_notifications(self, monitor):
        """测试轮询触发通知."""
        observer = MockObserver()
        monitor.register_observer(observer)
        
        # Mock fetch方法返回S-1文件
        monitor.fetch = Mock(return_value=[
            {"cik": "000123", "form_type": "S-1"},
            {"cik": "000456", "form_type": "424B4"},
        ])
        
        monitor.poll()
        
        assert len(observer.s1_calls) == 1
        assert len(observer.b4_calls) == 1


class TestEdgarIPOCrawler:
    """测试EDGAR IPO爬虫."""
    
    @pytest.fixture
    def crawler(self):
        return EdgarIPOCrawler()
    
    def test_filing_to_event(self, crawler):
        """测试转换文件到事件."""
        filing = {
            "cik": "0001234567",
            "company_name": "Test Company",
            "filed_date": "2024-01-15",
            "filing_url": "http://test.com/s1",
        }
        
        event = crawler._filing_to_event(filing)
        
        assert event is not None
        assert event.cik == "0001234567"
        assert event.company_name == "Test Company"
        assert event.s1_filing_url == "http://test.com/s1"
    
    def test_filing_to_event_invalid_date(self, crawler):
        """测试无效日期转换."""
        filing = {
            "cik": "000123",
            "filed_date": "invalid-date",
        }
        
        event = crawler._filing_to_event(filing)
        
        # 应该返回事件，但日期为None或今天
        assert event is not None
