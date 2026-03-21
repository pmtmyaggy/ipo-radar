"""基本面筛选模块 - 基于财务指标筛选IPO标的.

负责解析S-1文件，提取关键财务指标，并基于规则快速评分。
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.crawler.api import CrawlerAPI
from src.crawler.models.schemas import QuickScore, S1Metrics
from src.crawler.models.database import DatabaseManager

logger = logging.getLogger(__name__)


# 十大承销商名单
TOP_TEN_UNDERWRITERS = [
    "Goldman Sachs",
    "Morgan Stanley", 
    "J.P. Morgan",
    "Bank of America",
    "Citigroup",
    "Credit Suisse",
    "Barclays",
    "UBS",
    "Deutsche Bank",
    "Wells Fargo",
]


@dataclass
class ScreenCriteria:
    """筛选条件."""
    min_revenue_growth: Optional[float] = None
    min_gross_margin: Optional[float] = None
    min_cash_runway_months: Optional[float] = None
    max_debt_to_assets: Optional[float] = None
    min_market_cap: Optional[float] = None
    required_underwriters: Optional[list] = None


class FundamentalScreener:
    """基本面筛选器.
    
    基于S-1文件中的财务数据进行评分。
    """
    
    def __init__(
        self,
        crawler: Optional[CrawlerAPI] = None,
        db_manager: Optional[DatabaseManager] = None,
    ):
        """初始化筛选器."""
        self.crawler = crawler or CrawlerAPI()
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
    
    def screen(self, tickers: list[str], criteria: Optional[ScreenCriteria] = None) -> list[str]:
        """根据基本面条件筛选股票.
        
        Args:
            tickers: 股票代码列表
            criteria: 筛选条件
        
        Returns:
            通过筛选的股票代码列表
        """
        passed = []
        
        for ticker in tickers:
            try:
                score = self.score_ipo(ticker)
                
                if criteria:
                    # 根据条件筛选
                    if self._meets_criteria(score, criteria):
                        passed.append(ticker)
                else:
                    # 默认：PASS或REVIEW
                    if score.verdict in ["PASS", "REVIEW"]:
                        passed.append(ticker)
                        
            except Exception as e:
                self.logger.warning(f"Failed to screen {ticker}: {e}")
                continue
        
        return passed
    
    def _meets_criteria(self, score: QuickScore, criteria: ScreenCriteria) -> bool:
        """检查是否满足筛选条件."""
        # 简化实现
        return score.verdict == "PASS"
    
    def score_ipo(self, ticker: str) -> QuickScore:
        """对指定IPO进行基本面评分.
        
        评分规则（总分100分）：
        - 营收增速 >20%: +25分, 10-20%: +15分, <10%: 0
        - 毛利率 >60%: +20分, 40-60%: +12分, <40%: 0  
        - 现金跑道 >18月: +20分, 12-18月: +10分, <12月: 0
        - 债务/资产 <0.3: +15分, 0.3-0.6: +8分, >0.6: 0
        - 前十承销商: +10分
        - 市值 >$1B: +10分, $500M-1B: +5分, <$500M: 0
        
        总分 >= 60: PASS, < 40: FAIL, 40-60: REVIEW
        
        Args:
            ticker: 股票代码
        
        Returns:
            QuickScore评分结果
        """
        # 获取S-1数据
        metrics = self._get_s1_metrics(ticker)
        
        if not metrics:
            return QuickScore(
                ticker=ticker,
                total=0,
                verdict="FAIL",
                details={},  # 空详情表示无数据
            )
        
        return self.calculate_quick_score(ticker, metrics)
    
    def _get_s1_metrics(self, ticker: str) -> Optional[S1Metrics]:
        """获取S-1关键指标."""
        # 尝试从数据库获取
        if self.db_manager:
            from src.crawler.models.database import S1FilingModel
            
            with self.db_manager.session_scope() as session:
                # 查找最新的S-1
                result = session.query(S1FilingModel).filter(
                    S1FilingModel.cik.in_(
                        session.query(IPOEventModel.cik).filter_by(ticker=ticker)
                    )
                ).order_by(S1FilingModel.filed_date.desc()).first()
                
                if result:
                    return S1Metrics(
                        revenue_growth=result.revenue_yoy_growth,
                        gross_margin=result.gross_margin,
                        cash_runway_months=self._calculate_cash_runway(result),
                        debt_to_assets=self._calculate_debt_ratio(result),
                        lead_underwriter=None,  # 需要从IPOEvent获取
                        market_cap=None,
                    )
        
        # 对于已上市股票，尝试从 Yahoo Finance 获取基本信息
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            info = stock.info
            
            if info:
                # 从 Yahoo Finance 获取可用数据
                market_cap = info.get('marketCap')
                revenue_growth = info.get('revenueGrowth')
                gross_margin = info.get('grossMargins')
                
                return S1Metrics(
                    revenue_growth=Decimal(str(revenue_growth)) if revenue_growth else None,
                    gross_margin=Decimal(str(gross_margin)) if gross_margin else None,
                    cash_runway_months=None,  # 无法直接获取
                    debt_to_assets=None,  # 无法直接获取
                    lead_underwriter=None,
                    market_cap=Decimal(str(market_cap)) if market_cap else None,
                )
        except Exception as e:
            logger.debug(f"Failed to get fundamentals from Yahoo Finance for {ticker}: {e}")
        
        return None
    
    def _calculate_cash_runway(self, s1_filing) -> Optional[Decimal]:
        """计算现金跑道（月）."""
        if not s1_filing.cash_and_equivalents or not s1_filing.net_income:
            return None
        
        # 简化计算：现金 / 月均亏损
        if s1_filing.net_income < 0:
            monthly_burn = abs(s1_filing.net_income) / 12
            if monthly_burn > 0:
                return s1_filing.cash_and_equivalents / monthly_burn
        
        return None
    
    def _calculate_debt_ratio(self, s1_filing) -> Optional[Decimal]:
        """计算债务/资产比."""
        if not s1_filing.total_debt:
            return Decimal("0")
        
        # 简化：假设总资产 = 现金 + 债务 + 其他（估算）
        # 实际应该从balance sheet获取
        estimated_assets = s1_filing.cash_and_equivalents or 0
        estimated_assets += s1_filing.total_debt
        estimated_assets *= Decimal("2")  # 粗略估算
        
        if estimated_assets > 0:
            return s1_filing.total_debt / estimated_assets
        
        return None
    
    def calculate_quick_score(self, ticker: str, metrics: S1Metrics) -> QuickScore:
        """计算快速评分.
        
        Args:
            ticker: 股票代码
            metrics: S-1关键指标
        
        Returns:
            QuickScore评分结果
        """
        score = 0
        details = {}
        
        # 1. 营收增速 (25分)
        if metrics.revenue_growth:
            growth = float(metrics.revenue_growth)
            if growth > 0.20:
                details["revenue"] = 25
            elif growth > 0.10:
                details["revenue"] = 15
            else:
                details["revenue"] = 0
            score += details["revenue"]
        else:
            details["revenue"] = 0
        
        # 2. 毛利率 (20分)
        if metrics.gross_margin:
            margin = float(metrics.gross_margin)
            if margin > 0.60:
                details["margin"] = 20
            elif margin > 0.40:
                details["margin"] = 12
            else:
                details["margin"] = 0
            score += details["margin"]
        else:
            details["margin"] = 0
        
        # 3. 现金跑道 (20分)
        if metrics.cash_runway_months:
            runway = float(metrics.cash_runway_months)
            if runway > 18:
                details["cash"] = 20
            elif runway > 12:
                details["cash"] = 10
            else:
                details["cash"] = 0
            score += details["cash"]
        else:
            details["cash"] = 0
        
        # 4. 债务水平 (15分)
        if metrics.debt_to_assets is not None:
            debt = float(metrics.debt_to_assets)
            if debt < 0.30:
                details["debt"] = 15
            elif debt < 0.60:
                details["debt"] = 8
            else:
                details["debt"] = 0
            score += details["debt"]
        else:
            details["debt"] = 0
        
        # 5. 承销商质量 (10分)
        if metrics.lead_underwriter:
            underwriter = metrics.lead_underwriter
            if any(top in underwriter for top in TOP_TEN_UNDERWRITERS):
                details["underwriter"] = 10
                score += 10
            else:
                details["underwriter"] = 0
        else:
            details["underwriter"] = 0
        
        # 6. 市值规模 (10分)
        if metrics.market_cap:
            cap = float(metrics.market_cap)
            if cap > 1_000_000_000:  # $1B
                details["market_cap"] = 10
            elif cap > 500_000_000:  # $500M
                details["market_cap"] = 5
            else:
                details["market_cap"] = 0
            score += details["market_cap"]
        else:
            details["market_cap"] = 0
        
        # 判定结果
        if score >= 60:
            verdict = "PASS"
        elif score < 40:
            verdict = "FAIL"
        else:
            verdict = "REVIEW"
        
        return QuickScore(
            ticker=ticker,
            total=score,
            details=details,
            verdict=verdict,
        )
    
    def batch_score(self, tickers: list[str]) -> list[QuickScore]:
        """批量评分并排序.
        
        Args:
            tickers: 股票代码列表
        
        Returns:
            按分数排序的QuickScore列表
        """
        results = []
        
        for ticker in tickers:
            try:
                score = self.score_ipo(ticker)
                results.append(score)
            except Exception as e:
                self.logger.warning(f"Failed to score {ticker}: {e}")
                continue
        
        # 按分数降序排序
        results.sort(key=lambda x: x.total, reverse=True)
        
        return results
    
    def get_top_picks(self, tickers: list[str], n: int = 10) -> list[QuickScore]:
        """获取排名前N的股票.
        
        Args:
            tickers: 股票代码列表
            n: 返回数量
        
        Returns:
            排名前N的QuickScore
        """
        all_scores = self.batch_score(tickers)
        
        # 只返回PASS的
        passed = [s for s in all_scores if s.verdict == "PASS"]
        
        return passed[:n]


def score_ipo_cli(ticker: str) -> None:
    """CLI入口: 对单个IPO评分.
    
    Usage: python -m src.screener TEST
    """
    screener = FundamentalScreener()
    score = screener.score_ipo(ticker)
    
    print(f"\n{'='*50}")
    print(f"基本面评分报告: {ticker}")
    print(f"{'='*50}")
    print(f"总分: {score.total}/100")
    print(f"判定: {score.verdict}")
    print(f"\n各维度得分:")
    for dimension, points in score.details.items():
        print(f"  - {dimension}: {points}分")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        ticker = sys.argv[1].upper()
        score_ipo_cli(ticker)
    else:
        print("Usage: python -m src.screener.fundamentals <ticker>")
