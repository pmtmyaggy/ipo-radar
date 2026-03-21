"""频率限制器 - 令牌桶算法实现.

提供可配置的请求频率限制，防止触发数据源的访问限制。
"""

import threading
import time
from typing import Optional


class RateLimiter:
    """令牌桶频率限制器.
    
    使用令牌桶算法实现平滑的请求频率限制。
    
    Attributes:
        rate: 每秒填充的令牌数（即每秒允许的请求数）
        burst: 桶容量（突发请求容量）
    
    Example:
        >>> limiter = RateLimiter(rate=5.0)  # 每秒5个请求
        >>> limiter.acquire()  # 阻塞直到获取令牌
        True
        >>> limiter.acquire(blocking=False)  # 非阻塞
        False  # 如果没有可用令牌
    """
    
    def __init__(self, rate: float = 1.0, burst: Optional[int] = None):
        """初始化频率限制器.
        
        Args:
            rate: 每秒允许的请求数，默认1.0
            burst: 桶容量，默认为1（无突发能力）
        """
        self.rate = max(0.0, rate)
        self.burst = max(1, burst) if burst else 1
        
        self._tokens = float(self.burst)
        self._last_update = time.monotonic()
        self._lock = threading.Lock()
    
    def _add_tokens(self) -> None:
        """根据时间流逝添加令牌."""
        now = time.monotonic()
        elapsed = now - self._last_update
        
        # 计算新增令牌数
        new_tokens = elapsed * self.rate
        self._tokens = min(self.burst, self._tokens + new_tokens)
        self._last_update = now
    
    def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """获取一个令牌.
        
        Args:
            blocking: 是否阻塞等待，默认True
            timeout: 阻塞等待的最大秒数，None表示无限等待
        
        Returns:
            True if token was acquired, False otherwise
        """
        with self._lock:
            self._add_tokens()
            
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            
            if not blocking:
                return False
            
            # 计算需要等待的时间
            tokens_needed = 1.0 - self._tokens
            wait_time = tokens_needed / self.rate
            
            if timeout is not None and wait_time > timeout:
                return False
        
        # 在锁外等待
        time.sleep(wait_time)
        
        with self._lock:
            self._add_tokens()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False
    
    def try_acquire(self) -> bool:
        """尝试获取令牌（非阻塞）.
        
        Returns:
            True if token was acquired, False otherwise
        """
        return self.acquire(blocking=False)
    
    @property
    def tokens(self) -> float:
        """当前可用令牌数."""
        with self._lock:
            self._add_tokens()
            return self._tokens
    
    @property
    def wait_time(self) -> float:
        """获取下一个令牌需要等待的秒数."""
        with self._lock:
            self._add_tokens()
            if self._tokens >= 1.0:
                return 0.0
            return (1.0 - self._tokens) / self.rate


class AdaptiveRateLimiter(RateLimiter):
    """自适应频率限制器.
    
    根据响应状态自动调整请求频率。
    遇到429（Too Many Requests）时自动降低频率。
    
    Attributes:
        initial_rate: 初始请求频率
        min_rate: 最小请求频率
        max_rate: 最大请求频率
        backoff_factor: 遇到限制后的回退倍数
        recovery_rate: 恢复频率的速度
    """
    
    def __init__(
        self,
        initial_rate: float = 1.0,
        min_rate: float = 0.1,
        max_rate: float = 10.0,
        backoff_factor: float = 0.5,
        recovery_rate: float = 0.1,
    ):
        """初始化自适应限制器.
        
        Args:
            initial_rate: 初始请求频率
            min_rate: 最小请求频率
            max_rate: 最大请求频率
            backoff_factor: 回退倍数（0.5表示频率减半）
            recovery_rate: 每次成功请求后增加的频率
        """
        super().__init__(rate=initial_rate, burst=1)
        self._initial_rate = initial_rate
        self._min_rate = min_rate
        self._max_rate = max_rate
        self._backoff_factor = backoff_factor
        self._recovery_rate = recovery_rate
    
    def report_success(self) -> None:
        """报告请求成功，尝试提高频率."""
        new_rate = min(self._max_rate, self.rate + self._recovery_rate)
        if new_rate != self.rate:
            with self._lock:
                self.rate = new_rate
    
    def report_rate_limit(self) -> None:
        """报告遇到频率限制，降低频率."""
        new_rate = max(self._min_rate, self.rate * self._backoff_factor)
        with self._lock:
            self.rate = new_rate
            # 清空令牌桶，强制等待
            self._tokens = 0.0
    
    def report_error(self, status_code: int) -> None:
        """根据HTTP状态码报告结果.
        
        Args:
            status_code: HTTP状态码
        """
        if status_code == 429:  # Too Many Requests
            self.report_rate_limit()
        elif 200 <= status_code < 300:
            self.report_success()
