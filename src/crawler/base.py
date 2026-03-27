"""爬虫抽象基类 - 所有爬虫模块的基类.

提供统一的能力：
- 频率限制
- 自动重试
- User-Agent管理
- 请求日志记录
- 数据去重
"""

import hashlib
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from .models.database import CrawlLogModel, DatabaseManager
from .utils.rate_limiter import RateLimiter
from .utils.retry import retry_with_backoff
from .utils.user_agent import UserAgentManager


class BaseCrawler(ABC):
    """爬虫抽象基类.

    所有爬虫模块必须继承此类，获得统一的基础能力。

    Attributes:
        name: 爬虫名称
        rate_limit: 每秒最大请求数
        max_retries: 最大重试次数
        retry_delay: 初始重试延迟（秒）
        db_manager: 数据库管理器
        session: 数据库会话

    Example:
        >>> class MyCrawler(BaseCrawler):
        ...     def fetch(self, **kwargs):
        ...         response = self._request("https://api.example.com/data")
        ...         return response.json()
    """

    def __init__(
        self,
        name: str,
        rate_limit: float = 1.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        db_manager: Optional[DatabaseManager] = None,
    ):
        """初始化爬虫.

        Args:
            name: 爬虫名称，用于日志和监控
            rate_limit: 每秒最大请求数，默认1.0
            max_retries: 最大重试次数，默认3
            retry_delay: 初始重试延迟（秒），默认1.0
            db_manager: 可选的数据库管理器
        """
        self.name = name
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.db_manager = db_manager

        # 初始化组件
        self._rate_limiter = RateLimiter(rate=rate_limit, burst=1)
        self._user_agent = UserAgentManager()
        self._logger = logging.getLogger(f"crawler.{name}")

        # 统计信息
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0
        self._start_time: Optional[float] = None

    def __enter__(self) -> "BaseCrawler":
        """上下文管理器入口."""
        self._start_time = time.time()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> Literal[False]:
        """上下文管理器出口，记录爬取日志."""
        self._log_crawl(exc_type, exc_val)
        return False

    @abstractmethod
    def fetch(self, **kwargs: Any) -> Any:
        """执行数据抓取.

        子类必须实现此方法。

        Args:
            **kwargs: 抓取参数

        Returns:
            抓取的数据

        Raises:
            NotImplementedError: 如果子类未实现
        """
        raise NotImplementedError(f"{self.name} must implement fetch()")

    def _request(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        use_rate_limit: bool = True,
        use_retry: bool = True,
        user_agent_type: str = "standard",
        **kwargs: Any,
    ) -> requests.Response:
        """发送HTTP请求.

        统一请求方法，内置频率限制、重试、日志记录。

        Args:
            url: 请求URL
            method: HTTP方法，默认GET
            headers: 自定义请求头
            use_rate_limit: 是否使用频率限制，默认True
            use_retry: 是否使用重试，默认True
            user_agent_type: User-Agent类型 (standard/browser/edgar)
            **kwargs: 传递给requests的其他参数

        Returns:
            Response对象
        """
        # 频率限制
        if use_rate_limit:
            self._rate_limiter.acquire()

        # 准备请求头（使用指定的User-Agent类型）
        request_headers = self._user_agent.get_headers(user_agent_type=user_agent_type)
        if headers:
            request_headers.update(headers)

        # 发送请求（带重试）
        start_time = time.time()

        if use_retry:
            response = self._request_with_retry(url, method, request_headers, **kwargs)
        else:
            # 过滤掉非 requests 参数
            request_kwargs = {
                k: v for k, v in kwargs.items() if k not in ("timeout", "user_agent_type")
            }
            response = requests.request(
                method=method,
                url=url,
                headers=request_headers,
                timeout=kwargs.get("timeout", 30),
                **request_kwargs,
            )

        # 记录请求日志
        duration = (time.time() - start_time) * 1000
        self._logger.debug(f"{method} {url} - {response.status_code} - {duration:.0f}ms")

        self._request_count += 1
        if response.ok:
            self._success_count += 1
        else:
            self._error_count += 1

        return response

    @retry_with_backoff(max_retries=3, exceptions=(requests.RequestException,))
    def _request_with_retry(
        self,
        url: str,
        method: str,
        headers: dict[str, str],
        **kwargs: Any,
    ) -> requests.Response:
        """带重试的请求方法."""
        # 过滤掉非 requests 参数
        request_kwargs = {
            k: v for k, v in kwargs.items() if k not in ("timeout", "user_agent_type")
        }
        return requests.request(
            method=method,
            url=url,
            headers=headers,
            timeout=kwargs.get("timeout", 30),
            **request_kwargs,
        )

    def _parse_html(self, html: str, parser: str = "lxml") -> BeautifulSoup:
        """解析HTML.

        Args:
            html: HTML字符串
            parser: 解析器类型，默认lxml

        Returns:
            BeautifulSoup对象
        """
        return BeautifulSoup(html, parser)

    def _save_to_db(
        self,
        data: Any,
        model_class: type,
        unique_key: str | None = None,
        session: Session | None = None,
    ) -> bool:
        """保存数据到数据库.

        内置幂等性检查，基于唯一键避免重复。

        Args:
            data: 要保存的数据（Pydantic模型或dict）
            model_class: SQLAlchemy模型类
            unique_key: 用于去重的唯一键字段名
            session: 可选的外部会话

        Returns:
            是否成功保存（True=新建，False=已存在或失败）
        """
        if self.db_manager is None:
            self._logger.warning("No database manager available, skipping save")
            return False

        try:
            # 转换为SQLAlchemy模型
            if hasattr(data, "model_dump"):
                # Pydantic v2
                data_dict = data.model_dump()
            elif hasattr(data, "dict"):
                # Pydantic v1
                data_dict = data.dict()
            else:
                data_dict = dict(data)

            # 幂等性检查
            if unique_key and unique_key in data_dict:
                existing = self._check_exists(
                    model_class, unique_key, data_dict[unique_key], session
                )
                if existing:
                    self._logger.debug(
                        f"Record with {unique_key}={data_dict[unique_key]} already exists"
                    )
                    return False

            # 保存数据
            db_obj = model_class(**data_dict)

            if session:
                session.add(db_obj)
                session.flush()
            else:
                with self.db_manager.session_scope() as s:
                    s.add(db_obj)

            return True

        except Exception as e:
            self._logger.error(f"Failed to save to database: {e}")
            return False

    def _check_exists(
        self,
        model_class: type,
        key: str,
        value: Any,
        session: Session | None = None,
    ) -> bool:
        """检查记录是否已存在."""
        if session is None:
            if self.db_manager is None:
                return False
            with self.db_manager.session_scope() as s:
                return (
                    s.query(model_class).filter(getattr(model_class, key) == value).first()
                    is not None
                )
        return (
            session.query(model_class).filter(getattr(model_class, key) == value).first()
            is not None
        )

    def _generate_id(self, *args: Any) -> str:
        """生成唯一ID.

        基于输入参数生成MD5哈希，用于幂等性。

        Args:
            *args: 用于生成ID的参数

        Returns:
            MD5哈希字符串
        """
        content = "|".join(str(arg) for arg in args)
        return hashlib.md5(content.encode()).hexdigest()

    def _log_crawl(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
    ) -> None:
        """记录爬取日志.

        Args:
            exc_type: 异常类型
            exc_val: 异常值
        """
        if self.db_manager is None:
            return

        try:
            duration_ms = None
            if self._start_time:
                duration_ms = int((time.time() - self._start_time) * 1000)

            log = CrawlLogModel(
                module=self.name,
                status="failure" if exc_type else "success",
                records_count=self._success_count,
                error_message=str(exc_val) if exc_val else None,
                started_at=(
                    datetime.fromtimestamp(self._start_time) if self._start_time else datetime.now()
                ),
                completed_at=datetime.now(),
                duration_ms=duration_ms,
            )

            with self.db_manager.session_scope() as session:
                session.add(log)

        except Exception as e:
            self._logger.error(f"Failed to log crawl: {e}")

    def get_stats(self) -> dict:
        """获取爬虫统计信息.

        Returns:
            统计信息字典
        """
        return {
            "name": self.name,
            "requests": self._request_count,
            "success": self._success_count,
            "errors": self._error_count,
            "success_rate": (
                self._success_count / self._request_count * 100 if self._request_count > 0 else 0
            ),
        }

    def reset_stats(self) -> None:
        """重置统计信息."""
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0
