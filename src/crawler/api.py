"""爬虫系统对外API.

提供统一的数据访问接口，整合所有爬虫模块。
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from .models.database import DatabaseManager
from .models.schemas import (
    IPOEvent,
    StockBar,
    NewsItem,
    EarningsReport,
    LockupInfo,
    InstitutionalHolding,
)
from .ipo_calendar import IPOCalendarAggregator
from .edgar_monitor import EdgarIPOCrawler, EdgarMonitor
from .s1_parser import S1Parser
from .market_data import MarketDataCrawler, IntradaySnapshotCrawler
from .news_fetcher import GoogleNewsCrawler
from .earnings_fetcher import EarningsCrawler
from .holdings_fetcher import HoldingsFetcher, InstitutionalHoldingsAnalyzer

logger = logging.getLogger(__name__)


class CrawlerAPI:
    """爬虫系统对外API.
    
    提供统一的数据访问接口，自动处理：
    - 数据源选择和降级
    - 数据缓存
    - 错误处理
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """初始化API.
        
        Args:
            db_manager: 数据库管理器
        """
        self.db_manager = db_manager
        
        # 初始化各爬虫
        self._ipo_calendar = IPOCalendarAggregator(db_manager)
        self._edgar_crawler = EdgarIPOCrawler(db_manager)
        self._edgar_monitor = EdgarMonitor(db_manager)
        self._s1_parser = S1Parser(db_manager)
        self._market_data = MarketDataCrawler(db_manager)
        self._intraday = IntradaySnapshotCrawler(db_manager)
        self._news = GoogleNewsCrawler(db_manager)
        self._earnings = EarningsCrawler(db_manager)
        self._holdings = HoldingsFetcher(db_manager)
        self._holdings_analyzer = InstitutionalHoldingsAnalyzer(db_manager)
        
        self.logger = logging.getLogger(__name__)
    
    # ========================================================================
    # IPO日历接口
    # ========================================================================
    
    def get_upcoming_ipos(self, days: int = 14) -> list[IPOEvent]:
        """获取即将上市的IPO.
        
        Args:
            days: 未来多少天
        
        Returns:
            IPOEvent列表
        """
        return self._ipo_calendar.get_upcoming_ipos(days)
    
    def get_recent_ipos(self, days: int = 90) -> list[IPOEvent]:
        """获取近期上市的IPO.
        
        Args:
            days: 过去多少天
        
        Returns:
            IPOEvent列表
        """
        return self._ipo_calendar.get_recent_ipos(days)
    
    def refresh_ipo_calendar(self) -> int:
        """刷新IPO日历.
        
        从所有数据源获取最新IPO信息并保存到数据库。
        
        Returns:
            更新的IPO数量
        """
        events = self._ipo_calendar.fetch_all()
        
        count = 0
        if self.db_manager:
            from .models.database import IPOEventModel
            
            with self.db_manager.session_scope() as session:
                for event in events:
                    try:
                        db_event = IPOEventModel(**event.model_dump())
                        session.merge(db_event)
                        count += 1
                    except Exception as e:
                        self.logger.warning(f"Failed to save IPO event: {e}")
        
        return count
    
    # ========================================================================
    # S-1数据接口
    # ========================================================================
    
    def get_s1_data(self, cik: str) -> Optional[dict]:
        """获取S-1文件数据.
        
        Args:
            cik: SEC CIK编号
        
        Returns:
            S-1数据字典或None
        """
        # 先尝试从数据库获取
        if self.db_manager:
            from .models.database import S1FilingModel
            
            with self.db_manager.session_scope() as session:
                result = session.query(S1FilingModel).filter_by(cik=cik).first()
                if result:
                    return result.__dict__
        
        return None
    
    def parse_s1_filing(self, url: str, cik: str, filed_date: date) -> Optional[dict]:
        """解析S-1文件.
        
        Args:
            url: S-1文件URL
            cik: 公司CIK
            filed_date: 提交日期
        
        Returns:
            解析结果或None
        """
        filing = self._s1_parser.fetch(url=url, cik=cik, filed_date=filed_date)
        
        if filing and self.db_manager:
            from .models.database import S1FilingModel
            
            try:
                with self.db_manager.session_scope() as session:
                    db_filing = S1FilingModel(**filing.model_dump())
                    session.merge(db_filing)
            except Exception as e:
                self.logger.error(f"Failed to save S-1 filing: {e}")
        
        return filing.model_dump() if filing else None
    
    # ========================================================================
    # 行情数据接口
    # ========================================================================
    
    def get_stock_bars(
        self,
        ticker: str,
        start: date,
        end: Optional[date] = None,
    ) -> list[StockBar]:
        """获取股票历史行情.
        
        Args:
            ticker: 股票代码
            start: 开始日期
            end: 结束日期（默认今天）
        
        Returns:
            StockBar列表
        """
        end = end or date.today()
        
        # 尝试从数据库获取
        if self.db_manager:
            bars = self._get_bars_from_db(ticker, start, end)
            if bars:
                return bars
        
        # 从yfinance获取
        bars = self._market_data.fetch(ticker=ticker, start=start, end=end)
        
        # 保存到数据库
        if bars and self.db_manager:
            self._save_bars_to_db(bars)
        
        return bars
    
    def _get_bars_from_db(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> list[StockBar]:
        """从数据库获取行情."""
        from .models.database import StockBarModel
        
        with self.db_manager.session_scope() as session:
            results = session.query(StockBarModel).filter(
                StockBarModel.ticker == ticker,
                StockBarModel.date >= start,
                StockBarModel.date <= end,
            ).all()
            
            return [StockBar(**r.__dict__) for r in results] if results else []
    
    def _save_bars_to_db(self, bars: list[StockBar]) -> None:
        """保存行情到数据库."""
        from .models.database import StockBarModel
        
        try:
            with self.db_manager.session_scope() as session:
                for bar in bars:
                    db_bar = StockBarModel(**bar.model_dump())
                    session.merge(db_bar)
        except Exception as e:
            self.logger.error(f"Failed to save bars to DB: {e}")
    
    def get_latest_price(self, ticker: str) -> Optional[float]:
        """获取最新价格.
        
        Args:
            ticker: 股票代码
        
        Returns:
            最新价格或None
        """
        return self._market_data.get_latest_price(ticker)
    
    def get_intraday_snapshots(self, tickers: list[str]) -> dict:
        """获取盘中快照.
        
        Args:
            tickers: 股票代码列表
        
        Returns:
            快照字典 {ticker: snapshot}
        """
        return self._intraday.fetch(tickers=tickers)
    
    def backfill_ipo_history(self, ticker: str, ipo_date: date) -> list[StockBar]:
        """回填IPO以来的历史数据.
        
        Args:
            ticker: 股票代码
            ipo_date: IPO日期
        
        Returns:
            StockBar列表
        """
        bars = self._market_data.backfill_history(ticker, ipo_date)
        
        if bars and self.db_manager:
            self._save_bars_to_db(bars)
        
        return bars
    
    # ========================================================================
    # 新闻接口
    # ========================================================================
    
    def get_news(
        self,
        ticker: str,
        company_name: str = "",
        days: int = 7,
    ) -> list[NewsItem]:
        """获取新闻.
        
        Args:
            ticker: 股票代码
            company_name: 公司名称
            days: 过去多少天
        
        Returns:
            NewsItem列表
        """
        return self._news.fetch(
            ticker=ticker,
            company_name=company_name,
            days=days,
        )
    
    # ========================================================================
    # 财报接口
    # ========================================================================
    
    def get_earnings(self, ticker: str) -> Optional[EarningsReport]:
        """获取财报数据.
        
        Args:
            ticker: 股票代码
        
        Returns:
            EarningsReport或None
        """
        return self._earnings.fetch(ticker=ticker)
    
    def get_next_earnings_date(self, ticker: str) -> Optional[date]:
        """获取下次财报日期.
        
        Args:
            ticker: 股票代码
        
        Returns:
            财报日期或None
        """
        return self._earnings.get_next_earnings_date(ticker)
    
    def get_upcoming_earnings(
        self,
        tickers: list[str],
        days_ahead: int = 30,
    ) -> list[dict]:
        """获取即将发布的财报.
        
        Args:
            tickers: 股票代码列表
            days_ahead: 未来多少天
        
        Returns:
            财报事件列表
        """
        return self._earnings.get_upcoming_earnings(tickers, days_ahead)
    
    # ========================================================================
    # 禁售期接口
    # ========================================================================
    
    def get_lockup_info(self, ticker: str, ipo_date: Optional[date] = None) -> Optional[LockupInfo]:
        """获取禁售期信息.
        
        优先从数据库获取，如果没有则根据IPO日期估算（默认180天）。
        
        Args:
            ticker: 股票代码
            ipo_date: IPO日期（可选）
        
        Returns:
            LockupInfo或None
        """
        try:
            # 1. 尝试从数据库获取
            import sqlite3
            conn = sqlite3.connect('data/ipo_radar.db')
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT ticker, lockup_expiry_date, supply_impact_pct FROM lockup_info WHERE ticker = ?',
                (ticker,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row:
                from src.crawler.models.schemas import LockupInfo
                from datetime import datetime
                expiry_date = None
                if row[1]:
                    try:
                        expiry_date = datetime.strptime(row[1], '%Y-%m-%d').date()
                    except:
                        pass
                
                # 需要从数据库获取更多字段
                conn2 = sqlite3.connect('data/ipo_radar.db')
                cursor2 = conn2.cursor()
                cursor2.execute(
                    'SELECT ipo_date, lockup_days FROM lockup_info WHERE ticker = ?',
                    (ticker,)
                )
                row2 = cursor2.fetchone()
                conn2.close()
                
                ipo_date = None
                lockup_days = 180
                if row2:
                    if row2[0]:
                        try:
                            ipo_date = datetime.strptime(row2[0], '%Y-%m-%d').date()
                        except:
                            pass
                    if row2[1]:
                        lockup_days = row2[1]
                
                return LockupInfo(
                    ticker=row[0],
                    ipo_date=ipo_date or expiry_date,  # 如果缺少ipo_date，用expiry_date代替
                    lockup_days=lockup_days,
                    lockup_expiry_date=expiry_date,
                    supply_impact_pct=Decimal(str(row[2])) if row[2] else Decimal("0.20"),
                )
            
            # 2. 尝试从IPO日期估算（默认180天锁定期）
            if ipo_date is None:
                # 从数据库获取IPO日期
                conn = sqlite3.connect('data/ipo_radar.db')
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT expected_date FROM ipo_events WHERE ticker = ?',
                    (ticker,)
                )
                row = cursor.fetchone()
                conn.close()
                
                if row and row[0]:
                    from datetime import datetime
                    try:
                        ipo_date = datetime.strptime(row[0], '%Y-%m-%d').date()
                    except:
                        pass
            
            if ipo_date:
                from src.crawler.models.schemas import LockupInfo
                from datetime import timedelta
                
                # 默认180天锁定期
                lockup_days = 180
                lockup_date = ipo_date + timedelta(days=lockup_days)
                
                return LockupInfo(
                    ticker=ticker,
                    ipo_date=ipo_date,
                    lockup_days=lockup_days,
                    lockup_expiry_date=lockup_date,
                    supply_impact_pct=Decimal("0.20"),  # 默认20%
                )
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get lockup info for {ticker}: {e}")
            return None
    
    def get_upcoming_lockup_expiries(
        self,
        days_ahead: int = 30,
    ) -> list[LockupInfo]:
        """获取即将到期的禁售期.
        
        Args:
            days_ahead: 未来多少天
        
        Returns:
            LockupInfo列表
        """
        # TODO: 从数据库查询
        return []
    
    # ========================================================================
    # EDGAR监控接口
    # ========================================================================
    
    def start_edgar_monitoring(self, callback=None) -> None:
        """启动EDGAR监控.
        
        Args:
            callback: 新文件回调函数
        """
        self._edgar_monitor.start_monitoring(callback)
    
    def stop_edgar_monitoring(self) -> None:
        """停止EDGAR监控."""
        self._edgar_monitor.stop_monitoring()
    
    def get_recent_s1_filings(self, days: int = 7) -> list[dict]:
        """获取最近的S-1文件.
        
        Args:
            days: 过去多少天
        
        Returns:
            S-1文件列表
        """
        return self._edgar_monitor.get_s1_filings(days)
    
    # ========================================================================
    # 机构持仓接口 (PRD 3.6模块)
    # ========================================================================
    
    def get_institutional_holdings(
        self,
        ticker: Optional[str] = None,
        cik: Optional[str] = None,
        quarter: Optional[str] = None,
    ) -> list[InstitutionalHolding]:
        """获取机构持仓数据.
        
        PRD 3.6: 从13F报告获取机构持仓信息。
        
        Args:
            ticker: 股票代码（可选）
            cik: 机构CIK（可选）
            quarter: 季度，格式 '2024-Q1'（可选）
        
        Returns:
            InstitutionalHolding列表
        """
        return self._holdings.fetch(
            ticker=ticker,
            cik=cik,
            quarter=quarter,
        )
    
    def analyze_holdings_change(
        self,
        ticker: str,
        current_quarter: str,
        previous_quarter: str,
    ) -> dict:
        """分析机构持仓季度变化.
        
        PRD 3.6: 计算新增机构数量、总持仓变化、前十大持仓机构。
        
        Args:
            ticker: 股票代码
            current_quarter: 当前季度，如 '2024-Q1'
            previous_quarter: 上一季度，如 '2023-Q4'
        
        Returns:
            分析结果字典:
                - new_institutions: 新增机构数量
                - dropped_institutions: 退出机构数量
                - total_institutions: 总机构数
                - total_shares_change: 总持股数变化
                - total_value_change_pct: 总市值变化%
                - top_10_holders: 前十大持仓机构列表
        """
        return self._holdings_analyzer.analyze_holdings_change(
            ticker=ticker,
            current_quarter=current_quarter,
            previous_quarter=previous_quarter,
        )


# 便捷函数
def get_crawler_api(db_manager: Optional[DatabaseManager] = None) -> CrawlerAPI:
    """获取CrawlerAPI实例.
    
    Args:
        db_manager: 可选的数据库管理器
    
    Returns:
        CrawlerAPI实例
    """
    return CrawlerAPI(db_manager)
