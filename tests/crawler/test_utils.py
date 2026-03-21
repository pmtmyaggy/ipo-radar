"""测试工具函数."""

import time
import pytest

from src.crawler.utils.rate_limiter import RateLimiter, AdaptiveRateLimiter
from src.crawler.utils.retry import retry_with_backoff, RetryError
from src.crawler.utils.user_agent import UserAgentManager


class TestRateLimiter:
    """测试频率限制器."""
    
    def test_basic_limiting(self):
        """测试基本限流功能."""
        limiter = RateLimiter(rate=10.0)  # 每秒10个请求
        
        # 第一次应该立即获得令牌
        assert limiter.acquire(blocking=False) is True
        
        # 连续请求应该失败（桶已空）
        assert limiter.acquire(blocking=False) is False
    
    def test_token_refill(self):
        """测试令牌补充."""
        limiter = RateLimiter(rate=10.0)  # 每秒10个
        
        # 消耗一个令牌
        limiter.acquire(blocking=False)
        
        # 等待令牌补充
        time.sleep(0.15)  # 等待超过0.1秒（1/10）
        
        # 应该可以获得令牌
        assert limiter.acquire(blocking=False) is True
    
    def test_burst_capacity(self):
        """测试突发容量."""
        limiter = RateLimiter(rate=1.0, burst=5)  # 每秒1个，桶容量5
        
        # 应该可以连续获得5个令牌
        success_count = 0
        for _ in range(5):
            if limiter.acquire(blocking=False):
                success_count += 1
        
        assert success_count == 5
        
        # 第6个应该失败
        assert limiter.acquire(blocking=False) is False


class TestAdaptiveRateLimiter:
    """测试自适应频率限制器."""
    
    def test_rate_limit_backoff(self):
        """测试遇到限制后的回退."""
        limiter = AdaptiveRateLimiter(
            initial_rate=5.0,
            min_rate=0.5,
            backoff_factor=0.5,
        )
        
        initial_rate = limiter.rate
        
        # 报告遇到频率限制
        limiter.report_rate_limit()
        
        # 频率应该降低
        assert limiter.rate < initial_rate
        assert limiter.rate >= 0.5  # 但不低于最小值
    
    def test_success_recovery(self):
        """测试成功后恢复."""
        limiter = AdaptiveRateLimiter(
            initial_rate=1.0,
            max_rate=5.0,
            recovery_rate=0.5,
        )
        
        # 先降低频率
        limiter.report_rate_limit()
        reduced_rate = limiter.rate
        
        # 报告成功
        limiter.report_success()
        
        # 频率应该提高
        assert limiter.rate > reduced_rate


class TestRetryDecorator:
    """测试重试装饰器."""
    
    def test_successful_call(self):
        """测试成功调用不重试."""
        call_count = 0
        
        @retry_with_backoff(max_retries=3)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = success_func()
        
        assert result == "success"
        assert call_count == 1  # 只调用一次
    
    def test_retry_on_failure(self):
        """测试失败时重试."""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, delay=0.01)
        def fail_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")
        
        with pytest.raises(RetryError):
            fail_func()
        
        # 应该调用3次（初始 + 2次重试）
        assert call_count == 3
    
    def test_specific_exceptions(self):
        """测试只捕获特定异常."""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, delay=0.01, exceptions=(ValueError,))
        def raise_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Should not retry")
        
        with pytest.raises(TypeError):
            raise_type_error()
        
        # 不应该重试
        assert call_count == 1


class TestUserAgentManager:
    """测试User-Agent管理器."""
    
    def test_standard_ua(self):
        """测试标准User-Agent."""
        manager = UserAgentManager(contact_email="test@example.com")
        ua = manager.get_standard()
        
        assert "IPO-Radar" in ua
        assert "test@example.com" in ua
    
    def test_edgar_ua(self):
        """测试EDGAR专用User-Agent."""
        manager = UserAgentManager(contact_email="test@example.com")
        ua = manager.get_edgar()
        
        # EDGAR格式：AppName email
        parts = ua.split()
        assert len(parts) == 2
        assert "IPO-Radar" in parts[0]
        assert "@" in parts[1]
    
    def test_get_headers(self):
        """测试获取请求头."""
        manager = UserAgentManager()
        headers = manager.get_headers()
        
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
    
    def test_email_validation(self):
        """测试邮箱验证."""
        manager = UserAgentManager()
        
        assert manager.validate_email("test@example.com") is True
        assert manager.validate_email("invalid-email") is False
        assert manager.validate_email("test@") is False
