"""重试机制 - 指数退避重试装饰器.

提供带指数退避的重试机制，自动处理临时性错误。
"""

import functools
import logging
import random
import time
from typing import Any, Callable, Optional, Tuple, Type, Union


class RetryError(Exception):
    """重试失败异常."""
    
    def __init__(self, message: str, last_exception: Optional[Exception] = None):
        super().__init__(message)
        self.last_exception = last_exception


def retry_with_backoff(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
    logger: Optional[logging.Logger] = None,
) -> Callable:
    """指数退避重试装饰器.
    
    当函数抛出指定异常时，自动重试，每次重试间隔呈指数增长。
    
    Args:
        max_retries: 最大重试次数，默认3
        delay: 初始重试延迟（秒），默认1.0
        backoff: 退避倍数，默认2.0（即 1s, 2s, 4s...）
        max_delay: 最大重试延迟（秒），默认60
        exceptions: 需要捕获的异常类型元组，默认捕获所有Exception
        on_retry: 每次重试时的回调函数，接收(异常, 重试次数)
        logger: 可选的日志记录器
    
    Returns:
        装饰器函数
    
    Example:
        >>> @retry_with_backoff(max_retries=3, delay=1.0)
        ... def fetch_data():
        ...     return requests.get("https://api.example.com/data")
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt >= max_retries:
                        # 重试次数用尽
                        msg = f"Function {func.__name__} failed after {max_retries} retries"
                        if logger:
                            logger.error(msg, exc_info=e)
                        raise RetryError(msg, last_exception=e) from e
                    
                    # 计算等待时间（添加随机抖动）
                    jitter = random.uniform(0, 0.1 * current_delay)
                    wait_time = min(current_delay + jitter, max_delay)
                    
                    if logger:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}), "
                            f"retrying in {wait_time:.1f}s: {e}"
                        )
                    
                    if on_retry:
                        on_retry(e, attempt + 1)
                    
                    time.sleep(wait_time)
                    
                    # 指数退避
                    current_delay *= backoff
            
            # 不应该执行到这里
            raise RetryError("Unexpected end of retry loop", last_exception=last_exception)
        
        return wrapper
    return decorator


def retry_on_status_code(
    status_codes: Tuple[int, ...] = (429, 500, 502, 503, 504),
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
) -> Callable:
    """基于HTTP状态码的重试装饰器.
    
    专门用于requests请求，根据响应状态码决定是否重试。
    
    Args:
        status_codes: 需要重试的HTTP状态码，默认(429, 500, 502, 503, 504)
        max_retries: 最大重试次数，默认3
        delay: 初始延迟，默认1.0
        backoff: 退避倍数，默认2.0
    
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                response = func(*args, **kwargs)
                
                # 检查状态码
                if hasattr(response, 'status_code'):
                    if response.status_code not in status_codes:
                        return response
                    
                    if attempt >= max_retries:
                        return response
                    
                    # 特殊处理429（Too Many Requests）
                    if response.status_code == 429:
                        # 尝试获取Retry-After头
                        retry_after = response.headers.get('Retry-After')
                        if retry_after:
                            try:
                                wait_time = int(retry_after)
                            except ValueError:
                                wait_time = current_delay
                        else:
                            wait_time = current_delay
                    else:
                        wait_time = current_delay
                    
                    time.sleep(wait_time)
                    current_delay = min(current_delay * backoff, 60.0)
                else:
                    return response
            
            return response
        
        return wrapper
    return decorator


class RetryManager:
    """重试管理器.
    
    提供更细粒度的重试控制，支持动态调整重试策略。
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ):
        """初始化重试管理器."""
        self.max_retries = max_retries
        self.delay = delay
        self.backoff = backoff
        self.exceptions = exceptions
        
        self._retry_count = 0
        self._success_count = 0
        self._failure_count = 0
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """执行函数，带重试逻辑."""
        current_delay = self.delay
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                self._success_count += 1
                return result
                
            except self.exceptions as e:
                last_exception = e
                self._retry_count += 1
                
                if attempt >= self.max_retries:
                    self._failure_count += 1
                    raise RetryError(
                        f"Failed after {self.max_retries} retries"
                    ) from e
                
                time.sleep(current_delay)
                current_delay *= self.backoff
        
        raise RetryError("Unexpected end of retry loop", last_exception=last_exception)
    
    def get_stats(self) -> dict:
        """获取重试统计."""
        return {
            "retries": self._retry_count,
            "successes": self._success_count,
            "failures": self._failure_count,
        }
    
    def reset_stats(self) -> None:
        """重置统计."""
        self._retry_count = 0
        self._success_count = 0
        self._failure_count = 0
