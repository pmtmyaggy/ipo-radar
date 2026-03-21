"""财报数据爬虫 - 从yfinance获取财报数据."""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

import yfinance as yf

from .base import BaseCrawler
from .models.schemas import EarningsReport, GuidanceType

logger = logging.getLogger(__name__)


class EarningsCrawler(BaseCrawler):
    """财报数据爬虫.
    
    使用yfinance获取财报日期和历史财报数据。
    """
    
    def __init__(self, db_manager=None):
        super().__init__(
            name="earnings",
            rate_limit=2.0,
            db_manager=db_manager,
        )
    
    def fetch(self, **kwargs) -> Optional[EarningsReport]:
        """获取财报数据.
        
        Args:
            ticker: 股票代码
            report_date: 财报日期（可选）
        """
        ticker = kwargs.get("ticker")
        
        if not ticker:
            return None
        
        try:
            yf_ticker = yf.Ticker(ticker)
            
            # 获取财报日历
            calendar = yf_ticker.calendar
            
            # 获取历史财报
            earnings = yf_ticker.earnings
            
            # 构建EarningsReport
            # 注意：yfinance的数据有限，这里简化处理
            report = self._parse_earnings_data(ticker, calendar, earnings)
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to fetch earnings for {ticker}: {e}")
            return None
    
    def get_next_earnings_date(self, ticker: str) -> Optional[date]:
        """获取下次财报日期."""
        try:
            yf_ticker = yf.Ticker(ticker)
            calendar = yf_ticker.calendar
            
            if calendar is not None and not calendar.empty:
                # 尝试获取Earnings Date
                if "Earnings Date" in calendar.index:
                    earnings_date = calendar.loc["Earnings Date"].iloc[0]
                    if isinstance(earnings_date, datetime):
                        return earnings_date.date()
            
            # 备用：从info中获取
            info = yf_ticker.info
            if "earningsDate" in info:
                timestamp = info["earningsDate"]
                if timestamp:
                    return datetime.fromtimestamp(timestamp).date()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get earnings date for {ticker}: {e}")
            return None
    
    def get_upcoming_earnings(self, tickers: list[str], days_ahead: int = 30) -> list[dict]:
        """获取即将发布的财报.
        
        Args:
            tickers: 股票代码列表
            days_ahead: 未来多少天
        
        Returns:
            财报事件列表
        """
        from datetime import timedelta
        
        upcoming = []
        cutoff = date.today() + timedelta(days=days_ahead)
        
        for ticker in tickers:
            try:
                earnings_date = self.get_next_earnings_date(ticker)
                
                if earnings_date and date.today() <= earnings_date <= cutoff:
                    upcoming.append({
                        "ticker": ticker,
                        "report_date": earnings_date,
                        "days_until": (earnings_date - date.today()).days,
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to check earnings for {ticker}: {e}")
                continue
        
        # 按日期排序
        upcoming.sort(key=lambda x: x["report_date"])
        
        return upcoming
    
    def _parse_earnings_data(
        self,
        ticker: str,
        calendar,
        earnings,
    ) -> Optional[EarningsReport]:
        """解析财报数据."""
        try:
            # 简化实现
            report = EarningsReport(
                ticker=ticker,
                report_date=date.today(),
                fiscal_quarter="Q1 2024",
                revenue=Decimal("0"),
                eps=Decimal("0"),
            )
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to parse earnings data: {e}")
            return None
