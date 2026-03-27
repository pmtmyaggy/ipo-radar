"""缓存层实现.

使用TTLCache实现内存缓存，减少重复查询。
"""

from datetime import datetime, timedelta
from collections.abc import Callable
import functools
from typing import Any, TypeVar, cast

# 尝试导入cachetools
try:
    from cachetools import TTLCache

    CACHETOOLS_AVAILABLE = True
except ImportError:
    CACHETOOLS_AVAILABLE = False

F = TypeVar("F", bound=Callable[..., Any])


class SimpleCache:
    """简单缓存实现（当cachetools不可用时）."""

    def __init__(self, maxsize: int = 100, ttl: int = 300):
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: dict[str, Any] = {}
        self._expires: dict[str, datetime] = {}

    def get(self, key: str) -> Any:
        """获取缓存值."""
        if key in self._cache:
            if datetime.now() < self._expires.get(key, datetime.min):
                return self._cache[key]
            else:
                # 过期，删除
                del self._cache[key]
                del self._expires[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """设置缓存值."""
        # 如果超过大小，删除最旧的
        if len(self._cache) >= self.maxsize:
            oldest_key = min(self._expires, key=lambda k: self._expires[k])
            del self._cache[oldest_key]
            del self._expires[oldest_key]

        self._cache[key] = value
        self._expires[key] = datetime.now() + timedelta(seconds=self.ttl)

    def clear(self) -> None:
        """清空缓存."""
        self._cache.clear()
        self._expires.clear()


class CacheManager:
    """缓存管理器."""

    _instance: "CacheManager | None" = None

    def __new__(cls) -> "CacheManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_cache()
        return cls._instance

    def _init_cache(self) -> None:
        """初始化缓存."""
        if CACHETOOLS_AVAILABLE:
            self._price_cache = TTLCache(maxsize=1000, ttl=60)  # 价格缓存1分钟
            self._fundamental_cache = TTLCache(maxsize=500, ttl=300)  # 基本面缓存5分钟
            self._news_cache = TTLCache(maxsize=200, ttl=600)  # 新闻缓存10分钟
        else:
            self._price_cache = SimpleCache(maxsize=1000, ttl=60)
            self._fundamental_cache = SimpleCache(maxsize=500, ttl=300)
            self._news_cache = SimpleCache(maxsize=200, ttl=600)

    def get_price(self, ticker: str) -> float | None:
        """获取缓存价格."""
        return cast(float | None, self._price_cache.get(ticker))

    def set_price(self, ticker: str, price: float) -> None:
        """缓存价格."""
        if CACHETOOLS_AVAILABLE:
            self._price_cache[ticker] = price
        else:
            self._price_cache.set(ticker, price)

    def get_fundamental(self, ticker: str) -> dict[str, Any] | None:
        """获取缓存基本面数据."""
        return cast(dict[str, Any] | None, self._fundamental_cache.get(ticker))

    def set_fundamental(self, ticker: str, data: dict[str, Any]) -> None:
        """缓存基本面数据."""
        if CACHETOOLS_AVAILABLE:
            self._fundamental_cache[ticker] = data
        else:
            self._fundamental_cache.set(ticker, data)

    def get_news(self, ticker: str) -> list[Any] | None:
        """获取缓存新闻."""
        return cast(list[Any] | None, self._news_cache.get(ticker))

    def set_news(self, ticker: str, news: list[Any]) -> None:
        """缓存新闻."""
        if CACHETOOLS_AVAILABLE:
            self._news_cache[ticker] = news
        else:
            self._news_cache.set(ticker, news)

    def clear_all(self) -> None:
        """清空所有缓存."""
        if CACHETOOLS_AVAILABLE:
            self._price_cache.clear()
            self._fundamental_cache.clear()
            self._news_cache.clear()
        else:
            self._price_cache.clear()
            self._fundamental_cache.clear()
            self._news_cache.clear()


# 全局缓存管理器实例
cache_manager = CacheManager()


def cached_price(func: F) -> F:
    """价格缓存装饰器."""

    @functools.wraps(func)
    def wrapper(self: Any, ticker: str, *args: Any, **kwargs: Any) -> Any:
        # 尝试从缓存获取
        cached = cache_manager.get_price(ticker)
        if cached is not None:
            return cached

        # 调用原函数
        result = func(self, ticker, *args, **kwargs)

        # 缓存结果
        if result is not None:
            cache_manager.set_price(ticker, result)

        return result

    return cast(F, wrapper)


def cached_fundamental(func: F) -> F:
    """基本面数据缓存装饰器."""

    @functools.wraps(func)
    def wrapper(self: Any, ticker: str, *args: Any, **kwargs: Any) -> Any:
        cached = cache_manager.get_fundamental(ticker)
        if cached is not None:
            return cached

        result = func(self, ticker, *args, **kwargs)

        if result is not None:
            cache_manager.set_fundamental(ticker, result)

        return result

    return cast(F, wrapper)


def cached_news(func: F) -> F:
    """新闻缓存装饰器."""

    @functools.wraps(func)
    def wrapper(self: Any, ticker: str, *args: Any, **kwargs: Any) -> Any:
        cached = cache_manager.get_news(ticker)
        if cached is not None:
            return cached

        result = func(self, ticker, *args, **kwargs)

        if result is not None:
            cache_manager.set_news(ticker, result)

        return result

    return cast(F, wrapper)
