"""新股监控模块 - 跟踪即将上市和近期上市的IPO.

负责维护观察名单，协调各分析模块的运行。
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, TypedDict

from src.crawler.api import CrawlerAPI
from src.crawler.models.database import DatabaseManager
from src.crawler.models.schemas import IPOEvent

logger = logging.getLogger(__name__)


@dataclass
class IPOTrackingStatus:
    """IPO跟踪状态."""
    ticker: str
    company_name: str
    ipo_date: date
    current_price: float | None = None
    price_vs_ipo: float | None = None  # 当前价 / 发行价
    days_since_ipo: int = 0
    status: str = "active"  # upcoming, active, mature

    # 各窗口活跃状态
    windows: dict[str, Any] = field(default_factory=dict)

    # 元数据
    last_updated: datetime = field(default_factory=datetime.now)
    data_sources: list[str] = field(default_factory=list)


class StockInfo(TypedDict, total=False):
    """股票基础信息."""

    ticker: str
    company_name: str
    ipo_date: date


class IPORadar:
    """新股雷达主类.
    
    维护观察名单，跟踪IPO状态，协调各分析模块。
    """

    # 自动添加规则
    AUTO_ADD_DAYS_BEFORE_IPO = 30  # IPO前30天自动添加
    AUTO_ADD_DAYS_AFTER_IPO = 90   # IPO后90天内跟踪
    AUTO_REMOVE_DAYS = 1500         # 上市1500天后自动移除

    def __init__(
        self,
        crawler: CrawlerAPI | None = None,
        db_manager: DatabaseManager | None = None,
    ):
        """初始化IPO雷达.
        
        Args:
            crawler: 爬虫API实例
            db_manager: 数据库管理器
        """
        self.crawler = crawler or CrawlerAPI()
        if db_manager is None:
            self.db_manager = DatabaseManager("sqlite:///data/ipo_radar.db")
        else:
            self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)

        # 观察名单缓存
        self._watchlist_cache: dict[str, IPOTrackingStatus] = {}
        self._cache_timestamp: datetime | None = None

    def get_watchlist(self, refresh: bool = False) -> list[IPOTrackingStatus]:
        """获取当前观察名单.
        
        Args:
            refresh: 是否强制刷新缓存
        
        Returns:
            跟踪状态列表
        """
        if refresh or self._is_cache_expired():
            self._refresh_cache()

        return list(self._watchlist_cache.values())

    def _is_cache_expired(self) -> bool:
        """检查缓存是否过期."""
        if self._cache_timestamp is None:
            return True

        # 缓存15分钟
        return datetime.now() - self._cache_timestamp > timedelta(minutes=15)

    def _refresh_cache(self) -> None:
        """刷新观察名单缓存."""
        if not self.db_manager:
            return

        from src.crawler.models.database import IPOEventModel

        with self.db_manager.session_scope() as session:
            # 获取所有活跃IPO
            today = date.today()
            cutoff = today - timedelta(days=self.AUTO_REMOVE_DAYS)

            results = session.query(IPOEventModel).filter(
                IPOEventModel.status.in_(["priced", "trading"]),
                IPOEventModel.expected_date >= cutoff,
            ).all()

            for result in results:
                status = self._db_to_tracking_status(result)
                self._watchlist_cache[status.ticker] = status

        self._cache_timestamp = datetime.now()
        self.logger.info(f"Refreshed watchlist cache: {len(self._watchlist_cache)} stocks")

    def _db_to_tracking_status(self, db_event: Any) -> IPOTrackingStatus:
        """将数据库事件转换为跟踪状态."""
        today = date.today()

        ipo_date = db_event.expected_date or today
        days_since = (today - ipo_date).days

        # 确定状态
        if days_since < 0:
            status = "upcoming"
        elif days_since < self.AUTO_ADD_DAYS_AFTER_IPO:
            status = "active"
        else:
            status = "mature"

        # 获取最新价格
        current_price = None
        price_vs_ipo = None

        if db_event.final_price and db_event.final_price > 0:
            current_price = self.crawler.get_latest_price(db_event.ticker)
            if current_price:
                price_vs_ipo = current_price / float(db_event.final_price)

        return IPOTrackingStatus(
            ticker=db_event.ticker,
            company_name=db_event.company_name,
            ipo_date=ipo_date,
            current_price=current_price,
            price_vs_ipo=price_vs_ipo,
            days_since_ipo=max(0, days_since),
            status=status,
        )

    def add_to_watchlist(self, ticker: str, ipo_date: date | None = None) -> bool:
        """添加股票到观察名单.
        
        Args:
            ticker: 股票代码
            ipo_date: IPO日期（可选）
        
        Returns:
            是否成功添加
        """
        ticker = ticker.upper()

        try:
            # 获取股票信息
            info = self._get_stock_info(ticker, ipo_date)
            if not info:
                self.logger.warning(f"Could not get info for {ticker}")
                return False

            # 保存到数据库
            if self.db_manager:
                from src.crawler.models.database import IPOEventModel

                with self.db_manager.session_scope() as session:
                    db_event = IPOEventModel(
                        ticker=ticker,
                        company_name=str(info.get("company_name", "")),
                        expected_date=ipo_date or info.get("ipo_date", date.today()),
                        status="trading",
                    )
                    session.merge(db_event)

            # 刷新缓存
            self._refresh_cache()

            self.logger.info(f"Added {ticker} to watchlist")
            return True

        except Exception as e:
            self.logger.error(f"Failed to add {ticker} to watchlist: {e}")
            return False

    def _get_stock_info(self, ticker: str, ipo_date: date | None) -> StockInfo:
        """获取股票信息."""
        info: StockInfo = {"ticker": ticker}

        # 尝试从yfinance获取
        try:
            import yfinance as yf
            yf_ticker = yf.Ticker(ticker)
            yf_info = yf_ticker.info

            info["company_name"] = yf_info.get("longName") or yf_info.get("shortName", ticker)

            if not ipo_date:
                # 尝试获取IPO日期
                ipo_timestamp = yf_info.get("firstTradeDateEpochUtc")
                if ipo_timestamp:
                    info["ipo_date"] = datetime.fromtimestamp(ipo_timestamp).date()

        except Exception as e:
            self.logger.warning(f"Could not get yfinance info for {ticker}: {e}")
            info["company_name"] = ticker

        return info

    def remove_from_watchlist(self, ticker: str) -> bool:
        """从观察名单移除.
        
        Args:
            ticker: 股票代码
        
        Returns:
            是否成功移除
        """
        ticker = ticker.upper()

        try:
            if self.db_manager:
                from src.crawler.models.database import IPOEventModel

                with self.db_manager.session_scope() as session:
                    result = session.query(IPOEventModel).filter_by(ticker=ticker).first()
                    if result:
                        result.status = "removed"

            # 从缓存移除
            if ticker in self._watchlist_cache:
                del self._watchlist_cache[ticker]

            self.logger.info(f"Removed {ticker} from watchlist")
            return True

        except Exception as e:
            self.logger.error(f"Failed to remove {ticker} from watchlist: {e}")
            return False

    def scan_new_ipos(self) -> list[IPOEvent]:
        """扫描新的IPO并自动添加到观察名单.
        
        Returns:
            新发现的IPO列表
        """
        new_events = []

        # 获取即将上市的IPO
        upcoming = self.crawler.get_upcoming_ipos(days=self.AUTO_ADD_DAYS_BEFORE_IPO)

        # 获取近期上市的IPO
        recent = self.crawler.get_recent_ipos(days=self.AUTO_ADD_DAYS_AFTER_IPO)

        all_events = upcoming + recent

        for event in all_events:
            if not event.ticker:
                continue

            # 检查是否已在观察名单
            if event.ticker not in self._watchlist_cache:
                # 添加到数据库
                if self.db_manager:
                    from src.crawler.models.database import IPOEventModel

                    try:
                        with self.db_manager.session_scope() as session:
                            db_event = IPOEventModel(**event.model_dump())
                            session.merge(db_event)

                        new_events.append(event)
                        self.logger.info(f"Auto-added new IPO: {event.ticker}")

                    except Exception as e:
                        self.logger.warning(f"Failed to auto-add {event.ticker}: {e}")

        # 刷新缓存
        if new_events:
            self._refresh_cache()

        return new_events

    def update_status(self, ticker: str) -> IPOTrackingStatus | None:
        """更新指定IPO的状态.
        
        Args:
            ticker: 股票代码
        
        Returns:
            更新后的跟踪状态
        """
        ticker = ticker.upper()

        try:
            # 获取最新数据
            if self.db_manager:
                from src.crawler.models.database import IPOEventModel

                with self.db_manager.session_scope() as session:
                    result = session.query(IPOEventModel).filter_by(ticker=ticker).first()

                    if result:
                        status = self._db_to_tracking_status(result)
                        self._watchlist_cache[ticker] = status
                        return status

            return None

        except Exception as e:
            self.logger.error(f"Failed to update status for {ticker}: {e}")
            return None

    def get_active_tickers(self) -> list[str]:
        """获取活跃的股票代码列表.
        
        Returns:
            股票代码列表
        """
        watchlist = self.get_watchlist()

        active = [
            s.ticker for s in watchlist
            if s.status in ["upcoming", "active", "mature"]
        ]

        return active

    def run_full_scan(self) -> dict[str, int]:
        """运行完整扫描.
        
        1. 扫描新IPO
        2. 更新现有IPO状态
        3. 清理过期IPO
        
        Returns:
            扫描结果统计
        """
        stats: dict[str, int] = {
            "new_added": 0,
            "updated": 0,
            "removed": 0,
            "errors": 0,
        }

        # 扫描新IPO
        try:
            new_ipos = self.scan_new_ipos()
            stats["new_added"] = len(new_ipos)
        except Exception as e:
            self.logger.error(f"Error scanning new IPOs: {e}")
            stats["errors"] += 1

        # 更新现有IPO状态
        try:
            for ticker in list(self._watchlist_cache.keys()):
                updated = self.update_status(ticker)
                if updated:
                    stats["updated"] += 1
        except Exception as e:
            self.logger.error(f"Error updating statuses: {e}")
            stats["errors"] += 1

        # 清理过期IPO
        try:
            removed = self._cleanup_expired()
            stats["removed"] = removed
        except Exception as e:
            self.logger.error(f"Error cleaning up: {e}")
            stats["errors"] += 1

        self.logger.info(f"Full scan completed: {stats}")
        return stats

    def _cleanup_expired(self) -> int:
        """清理过期的IPO.
        
        Returns:
            移除的数量
        """
        today = date.today()
        cutoff = today - timedelta(days=self.AUTO_REMOVE_DAYS)

        removed = 0
        to_remove = []

        for ticker, status in self._watchlist_cache.items():
            if status.ipo_date < cutoff:
                to_remove.append(ticker)

        for ticker in to_remove:
            self.remove_from_watchlist(ticker)
            removed += 1

        return removed


class WatchlistManager:
    """观察名单管理器.
    
    提供高级的观察名单管理功能。
    """

    def __init__(self, radar: IPORadar):
        self.radar = radar

    def bulk_add(self, tickers: list[str]) -> dict[str, list[str]]:
        """批量添加.
        
        Returns:
            {success: [], failed: []}
        """
        results: dict[str, list[str]] = {"success": [], "failed": []}

        for ticker in tickers:
            if self.radar.add_to_watchlist(ticker):
                results["success"].append(ticker)
            else:
                results["failed"].append(ticker)

        return results

    def bulk_remove(self, tickers: list[str]) -> dict[str, list[str]]:
        """批量移除."""
        results: dict[str, list[str]] = {"success": [], "failed": []}

        for ticker in tickers:
            if self.radar.remove_from_watchlist(ticker):
                results["success"].append(ticker)
            else:
                results["failed"].append(ticker)

        return results

    def export_watchlist(self, format: str = "json") -> str:
        """导出观察名单."""
        import json

        watchlist = self.radar.get_watchlist()
        data = [
            {
                "ticker": s.ticker,
                "company_name": s.company_name,
                "ipo_date": s.ipo_date.isoformat(),
                "status": s.status,
            }
            for s in watchlist
        ]

        if format == "json":
            return json.dumps(data, indent=2)
        elif format == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=["ticker", "company_name", "ipo_date", "status"])
            writer.writeheader()
            writer.writerows(data)
            return output.getvalue()

        return ""
