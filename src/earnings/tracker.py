"""业绩追踪模块 - 跟踪IPO公司上市后的财务表现."""

import logging
from datetime import date, timedelta
from typing import Optional

from src.crawler.api import CrawlerAPI
from src.crawler.models.schemas import GuidanceType

logger = logging.getLogger(__name__)


class EarningsTracker:
    """业绩追踪器."""
    
    def __init__(self, crawler: Optional[CrawlerAPI] = None):
        """初始化."""
        self.crawler = crawler or CrawlerAPI()
        self.logger = logging.getLogger(__name__)
    
    def get_next_earnings_date(self, ticker: str) -> Optional[date]:
        """获取下次财报日期."""
        return self.crawler.get_next_earnings_date(ticker)
    
    def get_upcoming_earnings(self, tickers: list[str], days_ahead: int = 30) -> list[dict]:
        """获取即将发布的财报."""
        return self.crawler.get_upcoming_earnings(tickers, days_ahead)
    
    def analyze_earnings(self, ticker: str) -> str:
        """分析财报并生成信号.
        
        Returns:
            strong_buy, buy, neutral, caution
        """
        report = self.crawler.get_earnings(ticker)
        
        if not report:
            return "neutral"
        
        score = 0
        
        # EPS超预期
        if report.eps_surprise_pct and report.eps_surprise_pct > 0.05:
            score += 2
        elif report.eps_surprise_pct and report.eps_surprise_pct > 0:
            score += 1
        elif report.eps_surprise_pct and report.eps_surprise_pct < -0.05:
            score -= 2
        
        # 营收超预期
        if report.revenue_surprise_pct and report.revenue_surprise_pct > 0.05:
            score += 2
        elif report.revenue_surprise_pct and report.revenue_surprise_pct > 0:
            score += 1
        elif report.revenue_surprise_pct and report.revenue_surprise_pct < -0.05:
            score -= 2
        
        # 指引
        if report.guidance == GuidanceType.RAISED:
            score += 2
        elif report.guidance == GuidanceType.LOWERED:
            score -= 2
        
        # 映射到信号
        if score >= 4:
            return "strong_buy"
        elif score >= 2:
            return "buy"
        elif score >= 0:
            return "neutral"
        else:
            return "caution"
    
    def is_first_earnings(self, ticker: str, ipo_date: date) -> bool:
        """检查是否是首次财报."""
        # 简化：IPO后90天内的第一份财报认为是首次
        report = self.crawler.get_earnings(ticker)
        
        if report and report.is_first_public_report:
            return True
        
        # 根据日期判断
        next_date = self.get_next_earnings_date(ticker)
        if next_date:
            days_after_ipo = (next_date - ipo_date).days
            return 60 <= days_after_ipo <= 120
        
        return False


class EarningsCalendar:
    """财报日历."""
    
    def __init__(self, tracker: EarningsTracker):
        self.tracker = tracker
    
    def get_first_time_reports(self, tickers: list[str], days_ahead: int = 30) -> list[dict]:
        """获取首次财报."""
        upcoming = self.tracker.get_upcoming_earnings(tickers, days_ahead)
        
        # 过滤首次财报
        first_reports = [e for e in upcoming if e.get("is_first_report", False)]
        
        return first_reports
