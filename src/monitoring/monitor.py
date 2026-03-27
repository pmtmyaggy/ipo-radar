"""爬虫监控系统.

PRD 6.2 要求：
- 每个爬虫模块的最后成功运行时间
- 过去24小时的请求成功率
- 每个数据源的平均响应时间
- 数据库各表的记录数和最后更新时间
- 2小时未运行自动告警
"""

import logging
import threading
import time
from collections.abc import Callable
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text

from src.crawler.models.database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class CrawlerMetrics:
    """单个爬虫的监控指标."""

    crawler_name: str
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        """成功率（24小时内）."""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property
    def avg_response_time_ms(self) -> float:
        """平均响应时间."""
        if self.total_requests == 0:
            return 0.0
        return self.total_response_time_ms / self.total_requests

    @property
    def is_healthy(self) -> bool:
        """是否健康（2小时内成功运行过）."""
        if not self.last_success_time:
            return False
        return datetime.now() - self.last_success_time < timedelta(hours=2)


@dataclass
class DatabaseMetrics:
    """数据库监控指标."""

    table_name: str
    record_count: int = 0
    last_update_time: Optional[datetime] = None

    @property
    def is_stale(self) -> bool:
        """数据是否过时（2小时未更新）."""
        if not self.last_update_time:
            return True
        return datetime.now() - self.last_update_time > timedelta(hours=2)


@dataclass
class MonitorMetrics:
    """完整的监控指标."""

    timestamp: datetime = field(default_factory=datetime.now)
    crawler_metrics: Dict[str, CrawlerMetrics] = field(default_factory=dict)
    database_metrics: Dict[str, DatabaseMetrics] = field(default_factory=dict)

    def get_unhealthy_crawlers(self) -> List[str]:
        """获取不健康的爬虫列表."""
        return [name for name, metrics in self.crawler_metrics.items() if not metrics.is_healthy]

    def get_stale_tables(self) -> List[str]:
        """获取过时的数据表列表."""
        return [name for name, metrics in self.database_metrics.items() if metrics.is_stale]


class CrawlerMonitor:
    """爬虫监控器.

    收集各爬虫模块的运行指标，检测异常并触发告警。

    PRD 6.2 监控指标：
    - 每个爬虫模块的最后成功运行时间
    - 过去24小时的请求成功率
    - 每个数据源的平均响应时间
    - 数据库各表的记录数和最后更新时间
    """

    # 数据库表名列表
    MONITORED_TABLES = [
        "ipo_events",
        "stock_bars",
        "news_items",
        "s1_filings",
        "earnings_reports",
        "lockup_info",
        "institutional_holdings",
        "crawl_logs",
    ]

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """初始化监控器.

        Args:
            db_manager: 数据库管理器
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)

        # 存储各爬虫的指标
        self._metrics: Dict[str, CrawlerMetrics] = defaultdict(
            lambda: CrawlerMetrics(crawler_name="unknown")
        )

        # 线程锁
        self._lock = threading.Lock()

        # 上一次告警时间（防止重复告警）
        self._last_alert_time: Dict[str, datetime] = {}

        self.logger.info("CrawlerMonitor initialized")

    def record_request(
        self,
        crawler_name: str,
        success: bool,
        response_time_ms: float,
    ) -> None:
        """记录请求指标.

        Args:
            crawler_name: 爬虫名称
            success: 是否成功
            response_time_ms: 响应时间（毫秒）
        """
        with self._lock:
            metrics = self._metrics[crawler_name]
            metrics.crawler_name = crawler_name

            metrics.total_requests += 1
            metrics.total_response_time_ms += response_time_ms

            if success:
                metrics.successful_requests += 1
                metrics.last_success_time = datetime.now()
            else:
                metrics.failed_requests += 1
                metrics.last_failure_time = datetime.now()

        self.logger.debug(
            f"Recorded request for {crawler_name}: "
            f"success={success}, time={response_time_ms:.2f}ms"
        )

    def record_success(self, crawler_name: str, response_time_ms: float) -> None:
        """记录成功请求."""
        self.record_request(crawler_name, True, response_time_ms)

    def record_failure(self, crawler_name: str, response_time_ms: float = 0.0) -> None:
        """记录失败请求."""
        self.record_request(crawler_name, False, response_time_ms)

    def get_metrics(self, crawler_name: Optional[str] = None) -> MonitorMetrics:
        """获取监控指标.

        Args:
            crawler_name: 指定爬虫名称（None则返回所有）

        Returns:
            MonitorMetrics
        """
        with self._lock:
            crawler_metrics = {}

            if crawler_name:
                if crawler_name in self._metrics:
                    crawler_metrics[crawler_name] = self._metrics[crawler_name]
            else:
                crawler_metrics = dict(self._metrics)

        # 获取数据库指标
        database_metrics = self._get_database_metrics()

        return MonitorMetrics(
            timestamp=datetime.now(),
            crawler_metrics=crawler_metrics,
            database_metrics=database_metrics,
        )

    def _get_database_metrics(self) -> Dict[str, DatabaseMetrics]:
        """获取数据库指标."""
        metrics: Dict[str, DatabaseMetrics] = {}

        if not self.db_manager:
            return metrics

        try:
            with self.db_manager.session_scope() as session:
                for table_name in self.MONITORED_TABLES:
                    try:
                        # 获取记录数
                        result = session.execute(
                            text(f"SELECT COUNT(*) FROM {table_name}")
                        ).scalar()

                        # 获取最后更新时间
                        last_update = session.execute(
                            text(f"SELECT MAX(updated_at) FROM {table_name}")
                        ).scalar()

                        metrics[table_name] = DatabaseMetrics(
                            table_name=table_name,
                            record_count=result or 0,
                            last_update_time=last_update,
                        )

                    except Exception as e:
                        self.logger.warning(f"Failed to get metrics for {table_name}: {e}")
                        metrics[table_name] = DatabaseMetrics(
                            table_name=table_name,
                            record_count=0,
                        )

        except Exception as e:
            self.logger.error(f"Failed to get database metrics: {e}")

        return metrics

    def check_health(self) -> Dict[str, List[str]]:
        """健康检查.

        Returns:
            问题列表: {
                'unhealthy_crawlers': [],
                'stale_tables': [],
            }
        """
        metrics = self.get_metrics()

        return {
            "unhealthy_crawlers": metrics.get_unhealthy_crawlers(),
            "stale_tables": metrics.get_stale_tables(),
        }

    def should_alert(self, alert_type: str, cooldown_minutes: int = 60) -> bool:
        """检查是否应该发送告警（防止重复）.

        Args:
            alert_type: 告警类型
            cooldown_minutes: 冷却时间（分钟）

        Returns:
            是否应该告警
        """
        now = datetime.now()
        last_time = self._last_alert_time.get(alert_type)

        if not last_time:
            self._last_alert_time[alert_type] = now
            return True

        if now - last_time > timedelta(minutes=cooldown_minutes):
            self._last_alert_time[alert_type] = now
            return True

        return False

    def generate_report(self) -> str:
        """生成监控报告.

        Returns:
            报告文本
        """
        metrics = self.get_metrics()

        lines = [
            "📊 IPO-Radar 爬虫监控报告",
            f"生成时间: {metrics.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "=== 爬虫状态 ===",
        ]

        for name, crawler_metrics in metrics.crawler_metrics.items():
            status = "✅" if crawler_metrics.is_healthy else "❌"
            lines.append(
                f"{status} {name}: "
                f"成功率={crawler_metrics.success_rate:.1%}, "
                f"平均响应={crawler_metrics.avg_response_time_ms:.0f}ms, "
                f"最后成功={crawler_metrics.last_success_time.strftime('%H:%M') if crawler_metrics.last_success_time else 'Never'}"
            )

        lines.extend(
            [
                "",
                "=== 数据库状态 ===",
            ]
        )

        for name, db_metrics in metrics.database_metrics.items():
            status = "✅" if not db_metrics.is_stale else "⚠️"
            update_time = (
                db_metrics.last_update_time.strftime("%H:%M")
                if db_metrics.last_update_time
                else "Never"
            )
            lines.append(
                f"{status} {name}: " f"记录数={db_metrics.record_count}, " f"最后更新={update_time}"
            )

        # 检查问题
        issues = self.check_health()
        if issues["unhealthy_crawlers"] or issues["stale_tables"]:
            lines.extend(
                [
                    "",
                    "⚠️ 发现问题:",
                ]
            )

            for crawler in issues["unhealthy_crawlers"]:
                lines.append(f"  - 爬虫 {crawler} 超过2小时未成功运行")

            for table in issues["stale_tables"]:
                lines.append(f"  - 数据表 {table} 超过2小时未更新")

        return "\n".join(lines)


# 全局监控器实例
_global_monitor: Optional[CrawlerMonitor] = None


def get_monitor(db_manager: Optional[DatabaseManager] = None) -> CrawlerMonitor:
    """获取全局监控器实例（单例模式）."""
    global _global_monitor

    if _global_monitor is None:
        _global_monitor = CrawlerMonitor(db_manager)

    return _global_monitor


# 装饰器：自动记录爬虫请求指标
def monitored(crawler_name: str) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """监控装饰器.

    自动记录爬虫的请求指标。

    Example:
        @monitored("ipo_calendar")
        def fetch(self):
            # 爬取逻辑
            pass
    """

    def decorator(func: Callable[..., object]) -> Callable[..., object]:
        def wrapper(*args: object, **kwargs: object) -> object:
            monitor = get_monitor()
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                response_time = (time.time() - start_time) * 1000
                monitor.record_success(crawler_name, response_time)
                return result

            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                monitor.record_failure(crawler_name, response_time)
                raise

        return wrapper

    return decorator
