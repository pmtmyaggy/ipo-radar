"""测试IPO日历爬虫."""

import json
from datetime import date
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests

from src.crawler.ipo_calendar import (
    NasdaqIPOCalendarCrawler,
    IPOCalendarAggregator,
    IPOEvent,
    IPOStatus,
)


class TestNasdaqIPOCalendarCrawler:
    """测试Nasdaq IPO日历爬虫."""
    
    @pytest.fixture
    def crawler(self):
        return NasdaqIPOCalendarCrawler()
    
    @pytest.fixture
    def sample_nasdaq_response(self):
        """示例Nasdaq API响应."""
        return {
            "data": {
                "upcoming": {
                    "rows": [
                        {
                            "companyName": "Test Company Inc.",
                            "proposedTickerSymbol": "TEST",
                            "proposedExchange": "NASDAQ",
                            "expectedPricedDate": "06/15/2024",
                            "proposedSharePrice": "$15.00 - $18.00",
                            "sharesOffered": "10,000,000",
                            "leadManagers": "Goldman Sachs",
                            "sector": "Technology",
                        }
                    ]
                }
            }
        }
    
    def test_parse_row_upcoming(self, crawler):
        """测试解析即将上市的IPO数据行."""
        row = {
            "companyName": "Test Company Inc.",
            "proposedTickerSymbol": "TEST",
            "proposedExchange": "NASDAQ",
            "expectedPricedDate": "06/15/2024",
            "proposedSharePrice": "$15.00 - $18.00",
            "sharesOffered": "10,000,000",
            "leadManagers": "Goldman Sachs",
            "sector": "Technology",
        }
        
        event = crawler._parse_row(row, IPOStatus.FILED)
        
        assert event is not None
        assert event.ticker == "TEST"
        assert event.company_name == "Test Company Inc."
        assert event.exchange == "NASDAQ"
        assert event.expected_date == date(2024, 6, 15)
        assert event.price_range_low == 15.0
        assert event.price_range_high == 18.0
        assert event.shares_offered == 10000000
        assert event.lead_underwriter == "Goldman Sachs"
        assert event.sector == "Technology"
        assert event.status == IPOStatus.FILED
    
    def test_parse_row_priced(self, crawler):
        """测试解析已定价的IPO数据行."""
        row = {
            "companyName": "Priced Company",
            "symbol": "PRIC",
            "exchange": "NYSE",
            "pricedDate": "06/01/2024",
            "price": "$20.00",
            "sharesOffered": "5,000,000",
            "dealSize": "$100.0 M",
        }
        
        event = crawler._parse_row(row, IPOStatus.TRADING)
        
        assert event is not None
        assert event.ticker == "PRIC"
        assert event.final_price == 20.0
        assert event.deal_size_mm == 100.0
        assert event.status == IPOStatus.PRICED
    
    def test_parse_row_single_price(self, crawler):
        """测试解析单一价格（非区间）."""
        row = {
            "companyName": "Single Price Co",
            "proposedTickerSymbol": "SPC",
            "proposedSharePrice": "$25.00",
        }
        
        event = crawler._parse_row(row, IPOStatus.FILED)
        
        assert event is not None
        assert event.price_range_low == 25.0
        assert event.price_range_high == 25.0
    
    def test_parse_row_invalid_date(self, crawler):
        """测试解析无效日期."""
        row = {
            "companyName": "Bad Date Co",
            "proposedTickerSymbol": "BAD",
            "expectedPricedDate": "invalid-date",
        }
        
        event = crawler._parse_row(row, IPOStatus.FILED)
        
        assert event is not None
        assert event.expected_date is None
    
    def test_parse_response(self, crawler, sample_nasdaq_response):
        """测试解析API响应."""
        events = crawler._parse_response(sample_nasdaq_response, IPOStatus.FILED)
        
        assert len(events) == 1
        assert events[0].ticker == "TEST"
    
    def test_parse_response_empty(self, crawler):
        """测试解析空响应."""
        response = {"data": {}}
        events = crawler._parse_response(response, IPOStatus.FILED)
        
        assert len(events) == 0
    
    def test_parse_response_no_data(self, crawler):
        """测试解析无data字段的响应."""
        response = {}
        events = crawler._parse_response(response, IPOStatus.FILED)
        
        assert len(events) == 0
    
    @patch('src.crawler.ipo_calendar.requests.request')
    def test_fetch_upcoming_success(self, mock_request, crawler, sample_nasdaq_response):
        """测试成功获取即将上市的IPO."""
        mock_response = Mock()
        mock_response.json.return_value = sample_nasdaq_response
        mock_response.ok = True
        mock_request.return_value = mock_response
        
        events = crawler._fetch_upcoming()
        
        assert len(events) == 1
        assert events[0].ticker == "TEST"
    
    def test_fetch_network_error(self, crawler):
        """测试网络错误处理."""
        from src.crawler.utils.retry import RetryError
        
        # Mock _request 直接抛出异常（模拟重试后失败）
        with patch.object(crawler, '_request', side_effect=RetryError("Failed after retries")):
            events = crawler._fetch_upcoming()
            
            assert len(events) == 0


class TestIPOCalendarAggregator:
    """测试IPO日历聚合器."""
    
    @pytest.fixture
    def aggregator(self):
        return IPOCalendarAggregator()
    
    def test_deduplicate(self, aggregator):
        """测试去重功能."""
        events = [
            IPOEvent(ticker="A", company_name="A Co", status=IPOStatus.FILED, expected_date=date(2024, 6, 1)),
            IPOEvent(ticker="A", company_name="A Co", status=IPOStatus.FILED, expected_date=date(2024, 6, 1)),
            IPOEvent(ticker="B", company_name="B Co", status=IPOStatus.FILED, expected_date=date(2024, 6, 2)),
        ]
        
        unique = aggregator._deduplicate(events)
        
        assert len(unique) == 2
        tickers = [e.ticker for e in unique]
        assert "A" in tickers
        assert "B" in tickers
    
    def test_get_upcoming_ipos_filtering(self, aggregator):
        """测试获取即将上市的IPO过滤."""
        # 创建测试数据
        today = date.today()
        events = [
            IPOEvent(ticker="TODAY", company_name="Today Co", status=IPOStatus.FILED, expected_date=today),
            IPOEvent(ticker="FUTURE", company_name="Future Co", status=IPOStatus.FILED, expected_date=today + __import__('datetime').timedelta(days=10)),
            IPOEvent(ticker="PAST", company_name="Past Co", status=IPOStatus.FILED, expected_date=today - __import__('datetime').timedelta(days=1)),
            IPOEvent(ticker="FAR", company_name="Far Co", status=IPOStatus.FILED, expected_date=today + __import__('datetime').timedelta(days=40)),
        ]
        
        # Mock fetch_all
        aggregator.nasdaq.fetch = Mock(return_value=events)
        
        upcoming = aggregator.get_upcoming_ipos(days=30)
        
        tickers = [e.ticker for e in upcoming]
        assert "TODAY" in tickers
        assert "FUTURE" in tickers
        assert "PAST" not in tickers
        assert "FAR" not in tickers
    
    def test_get_upcoming_ipos_sorting(self, aggregator):
        """测试获取即将上市的IPO排序."""
        today = date.today()
        events = [
            IPOEvent(ticker="LATER", company_name="Later Co", status=IPOStatus.FILED, expected_date=today + __import__('datetime').timedelta(days=10)),
            IPOEvent(ticker="SOON", company_name="Soon Co", status=IPOStatus.FILED, expected_date=today + __import__('datetime').timedelta(days=2)),
        ]
        
        aggregator.nasdaq.fetch = Mock(return_value=events)
        
        upcoming = aggregator.get_upcoming_ipos(days=30)
        
        assert upcoming[0].ticker == "SOON"
        assert upcoming[1].ticker == "LATER"


class TestMockedIntegration:
    """集成测试（使用mock）."""
    
    @patch('src.crawler.ipo_calendar.requests.request')
    def test_full_flow_nasdaq(self, mock_request):
        """测试完整的Nasdaq数据获取流程."""
        # Mock响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "upcoming": {
                    "rows": [
                        {
                            "companyName": "Integration Test Co",
                            "proposedTickerSymbol": "INT",
                            "expectedPricedDate": "12/25/2024",
                            "proposedSharePrice": "$10.00 - $12.00",
                        }
                    ]
                }
            }
        }
        mock_response.ok = True
        mock_request.return_value = mock_response
        
        crawler = NasdaqIPOCalendarCrawler()
        events = crawler.fetch(upcoming=True, priced=False, filed=False)
        
        assert len(events) == 1
        assert events[0].ticker == "INT"
        assert events[0].company_name == "Integration Test Co"
