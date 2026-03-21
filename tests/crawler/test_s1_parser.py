"""测试S-1解析器."""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch

from src.crawler.s1_parser import S1Parser
from src.crawler.models.schemas import S1Filing


class TestS1Parser:
    """测试S-1解析器."""
    
    @pytest.fixture
    def parser(self):
        return S1Parser()
    
    @pytest.fixture
    def sample_s1_html(self):
        """示例S-1 HTML内容."""
        return """
        <html>
        <head><title>S-1 Test Company</title></head>
        <body>
            <h1>FORM S-1</h1>
            <h2>PROSPECTUS</h2>
            
            <h3>Selected Consolidated Financial Data</h3>
            <table>
                <tr><td>Revenue</td><td>$100,000,000</td><td>$80,000,000</td></tr>
                <tr><td>Gross Profit</td><td>$60,000,000</td><td>$45,000,000</td></tr>
            </table>
            
            <h3>Balance Sheet</h3>
            <table>
                <tr><td>Cash and cash equivalents</td><td>$50,000,000</td></tr>
                <tr><td>Total debt</td><td>$20,000,000</td></tr>
            </table>
            
            <h3>Shares Eligible for Future Sale</h3>
            <p>
                Subject to a 180-day lock-up period following the date of this prospectus.
                Our directors, officers, and holders of substantially all of our outstanding
                common stock have agreed not to sell any stock for 180 days.
            </p>
            
            <h3>Principal Stockholders</h3>
            <p>
                The following table sets forth information with respect to the beneficial
                ownership of our common stock by our directors, executive officers, and
                venture capital investors.
            </p>
            
            <h3>Use of Proceeds</h3>
            <p>
                We intend to use the net proceeds from this offering for general corporate
                purposes, including working capital, operating expenses, and capital expenditures.
            </p>
            
            <h3>Risk Factors</h3>
            <p>
                Investing in our common stock involves a high degree of risk. You should
                carefully consider the risks described below before making an investment decision.
            </p>
        </body>
        </html>
        """
    
    def test_parse_money_basic(self, parser):
        """测试基本货币解析."""
        assert parser._parse_money("$1,234,567") == Decimal("1234567")
        assert parser._parse_money("$100.5 million") == Decimal("100500000")
        assert parser._parse_money("$2B") == Decimal("2000000000")
        assert parser._parse_money("$500K") == Decimal("500000")
    
    def test_parse_money_negative(self, parser):
        """测试负数货币解析."""
        assert parser._parse_money("($500,000)") == Decimal("-500000")
    
    def test_parse_money_invalid(self, parser):
        """测试无效货币解析."""
        assert parser._parse_money("") is None
        assert parser._parse_money("N/A") is None
        assert parser._parse_money("unknown") is None
    
    def test_identify_holder_types(self, parser):
        """测试持有人类型识别."""
        text = "Our founders, CEO, and venture capital investors hold shares."
        holders = parser._identify_holder_types(text)
        
        assert "founders" in holders
        assert "vc" in holders
    
    def test_identify_holder_types_employees(self, parser):
        """测试识别员工持有人."""
        text = "Stock options granted to employees and restricted stock units."
        holders = parser._identify_holder_types(text)
        
        assert "employees" in holders
    
    def test_identify_holder_types_pe(self, parser):
        """测试识别PE持有人."""
        text = "Private equity sponsor and investment fund hold majority stake."
        holders = parser._identify_holder_types(text)
        
        assert "pe" in holders
    
    def test_parse_lockup_days(self, parser, sample_s1_html):
        """测试解析禁售期天数."""
        filing = S1Filing(cik="000123", filed_date=__import__('datetime').date(2024, 1, 1), s1_url="http://test.com")
        
        parser._parse_lockup(sample_s1_html, filing)
        
        assert filing.lockup_days == 180
    
    def test_parse_lockup_holders(self, parser, sample_s1_html):
        """测试解析禁售期持有人."""
        filing = S1Filing(cik="000123", filed_date=__import__('datetime').date(2024, 1, 1), s1_url="http://test.com")
        
        parser._parse_lockup(sample_s1_html, filing)
        
        assert "founders" in filing.locked_holders
        assert "vc" in filing.locked_holders
    
    def test_parse_use_of_proceeds(self, parser, sample_s1_html):
        """测试解析募集资金用途."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(sample_s1_html, 'lxml')
        filing = S1Filing(cik="000123", filed_date=__import__('datetime').date(2024, 1, 1), s1_url="http://test.com")
        
        parser._parse_use_of_proceeds(soup, sample_s1_html, filing)
        
        assert filing.use_of_proceeds is not None
        # 检查内容包含关键词（转换为小写比较）
        content = filing.use_of_proceeds.lower()
        assert "general corporate" in content or "corporate purposes" in content
    
    def test_parse_risk_factors(self, parser, sample_s1_html):
        """测试解析风险因素."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(sample_s1_html, 'lxml')
        filing = S1Filing(cik="000123", filed_date=__import__('datetime').date(2024, 1, 1), s1_url="http://test.com")
        
        parser._parse_risk_factors(soup, sample_s1_html, filing)
        
        assert filing.risk_factors_summary is not None
        assert "high degree of risk" in filing.risk_factors_summary.lower()
    
    def test_clean_html(self, parser):
        """测试HTML清理."""
        html = "<p>This is <b>bold</b> and <i>italic</i> text.</p>"
        clean = parser._clean_html(html)
        
        assert "<p>" not in clean
        assert "<b>" not in clean
        assert "bold" in clean
    
    @patch('src.crawler.s1_parser.requests.request')
    def test_fetch_success(self, mock_request, parser, sample_s1_html):
        """测试成功获取S-1."""
        mock_response = Mock()
        mock_response.text = sample_s1_html
        mock_response.ok = True
        mock_request.return_value = mock_response
        
        filing = parser.fetch(
            url="http://test.com/s1.html",
            cik="000123",
            filed_date=__import__('datetime').date(2024, 1, 1),
        )
        
        assert filing is not None
        assert filing.cik == "000123"
        assert filing.s1_url == "http://test.com/s1.html"
        assert filing.lockup_days == 180
    
    @patch('src.crawler.s1_parser.requests.request')
    def test_fetch_network_error(self, mock_request, parser):
        """测试网络错误."""
        import requests
        mock_request.side_effect = requests.RequestException("Network error")
        
        filing = parser.fetch(
            url="http://test.com/s1.html",
            cik="000123",
            filed_date=__import__('datetime').date(2024, 1, 1),
        )
        
        assert filing is None
    
    def test_fetch_no_url(self, parser):
        """测试缺少URL."""
        filing = parser.fetch(url="", cik="000123", filed_date=__import__('datetime').date(2024, 1, 1))
        assert filing is None
