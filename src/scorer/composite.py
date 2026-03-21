"""综合评分模块 - 多维度综合评估IPO投资价值.

整合所有子模块的输出，生成统一的投资决策报告。
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional, List

from src.radar.monitor import IPORadar
from src.screener.fundamentals import FundamentalScreener
from src.pattern.breakout_scanner import BreakoutScanner, PatternRecognizer
from src.lockup.tracker import LockupTracker
from src.sentiment.analyzer import SentimentAnalyzer
from src.earnings.tracker import EarningsTracker
from src.crawler.api import CrawlerAPI
from src.crawler.models.schemas import (
    OverallSignal,
    CompositeReport,
    WindowsStatus,
    FirstDayPullbackWindow,
    IPOBaseBreakoutWindow,
    LockupExpiryWindow,
    FirstEarningsWindow,
    SentimentResult,
    LockupStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class ScoreBreakdown:
    """评分明细."""
    ticker: str
    fundamental_score: float = 0.0  # 0-100
    pattern_score: float = 0.0  # 0-100
    sentiment_score: float = 0.0  # 0-100
    lockup_risk: float = 0.0  # 0-100 (越高越风险)
    earnings_score: float = 0.0  # 0-100
    
    @property
    def total_score(self) -> float:
        """加权综合评分."""
        weights = {
            "fundamental": 0.30,
            "pattern": 0.20,
            "sentiment": 0.15,
            "lockup": 0.15,
            "earnings": 0.20
        }
        return (
            self.fundamental_score * weights["fundamental"] +
            self.pattern_score * weights["pattern"] +
            self.sentiment_score * weights["sentiment"] +
            (100 - self.lockup_risk) * weights["lockup"] +
            self.earnings_score * weights["earnings"]
        )


class SignalAggregator:
    """信号聚合器.
    
    整合所有子模块的输出，生成综合决策报告。
    """
    
    def __init__(
        self,
        crawler: Optional[CrawlerAPI] = None,
        radar: Optional[IPORadar] = None,
        screener: Optional[FundamentalScreener] = None,
        pattern: Optional[PatternRecognizer] = None,
        lockup: Optional[LockupTracker] = None,
        sentiment: Optional[SentimentAnalyzer] = None,
        earnings: Optional[EarningsTracker] = None,
    ):
        """初始化信号聚合器."""
        self.crawler = crawler or CrawlerAPI()
        self.radar = radar or IPORadar(crawler=self.crawler)
        self.screener = screener or FundamentalScreener(crawler=self.crawler)
        self.pattern = pattern or PatternRecognizer()
        self.lockup = lockup or LockupTracker(crawler=self.crawler)
        self.sentiment = sentiment or SentimentAnalyzer(crawler=self.crawler)
        self.earnings = earnings or EarningsTracker(crawler=self.crawler)
        
        self.logger = logging.getLogger(__name__)
    
    def generate_report(self, ticker: str) -> CompositeReport:
        """生成综合报告.
        
        Args:
            ticker: 股票代码
        
        Returns:
            CompositeReport综合报告
        """
        ticker = ticker.upper()
        
        try:
            # 获取基础信息
            ipo_info = self._get_ipo_info(ticker)
            
            # 获取当前价格
            current_price = self.crawler.get_latest_price(ticker)
            ipo_price = ipo_info.get("ipo_price") if ipo_info else None
            price_vs_ipo = current_price / ipo_price if current_price and ipo_price else None
            
            # 评估四个窗口
            windows = self._evaluate_windows(ticker, ipo_info)
            
            # 基本面评分
            fundamental_score = self._get_fundamental_score(ticker)
            
            # 情绪分析
            sentiment = self._get_sentiment(ticker)
            
            # 判定综合信号
            overall_signal, signal_reasons = self._determine_overall_signal(
                windows, fundamental_score, sentiment
            )
            
            # 识别风险因素
            risk_factors = self._identify_risk_factors(windows, fundamental_score)
            
            report = CompositeReport(
                ticker=ticker,
                company_name=ipo_info.get("company_name") if ipo_info else None,
                ipo_date=ipo_info.get("ipo_date") if ipo_info else None,
                days_since_ipo=self._calculate_days_since_ipo(ipo_info),
                current_price=current_price,
                ipo_price=ipo_price,
                price_vs_ipo=price_vs_ipo,
                windows=windows,
                fundamental_score=int(fundamental_score),
                sentiment=sentiment,
                overall_signal=overall_signal,
                signal_reasons=signal_reasons,
                risk_factors=risk_factors,
                generated_at=datetime.now(),
            )
            
            return report
            
        except Exception as e:
            self.logger.error(f"Failed to generate report for {ticker}: {e}")
            # 返回空报告
            return CompositeReport(
                ticker=ticker,
                overall_signal=OverallSignal.NO_ACTION,
                signal_reasons=[f"Error generating report: {e}"],
            )
    
    def _get_ipo_info(self, ticker: str) -> Optional[dict]:
        """获取IPO信息."""
        try:
            # 从radar获取
            watchlist = self.radar.get_watchlist()
            for status in watchlist:
                if status.ticker == ticker:
                    return {
                        "ticker": status.ticker,
                        "company_name": status.company_name,
                        "ipo_date": status.ipo_date,
                        "ipo_price": None,  # 需要从数据库获取
                    }
            return None
        except Exception:
            return None
    
    def _calculate_days_since_ipo(self, ipo_info: Optional[dict]) -> Optional[int]:
        """计算上市天数."""
        if ipo_info and ipo_info.get("ipo_date"):
            return (date.today() - ipo_info["ipo_date"]).days
        return None
    
    def _evaluate_windows(self, ticker: str, ipo_info: Optional[dict]) -> WindowsStatus:
        """评估四个窗口状态."""
        windows = WindowsStatus()
        
        # 1. 首日回调窗口
        windows.first_day_pullback = self._evaluate_first_day_pullback(ticker, ipo_info)
        
        # 2. IPO底部突破窗口
        windows.ipo_base_breakout = self._evaluate_base_breakout(ticker, ipo_info)
        
        # 3. 禁售期到期窗口
        windows.lockup_expiry = self._evaluate_lockup_expiry(ticker)
        
        # 4. 首次财报窗口
        windows.first_earnings = self._evaluate_first_earnings(ticker, ipo_info)
        
        return windows
    
    def _evaluate_first_day_pullback(self, ticker: str, ipo_info: Optional[dict]) -> FirstDayPullbackWindow:
        """评估首日回调窗口."""
        window = FirstDayPullbackWindow(active=False)
        
        if not ipo_info:
            return window
        
        days_since = self._calculate_days_since_ipo(ipo_info)
        
        # 上市5天内算首日回调窗口
        if days_since and days_since <= 5:
            window.active = True
            
            # 检查是否破发后反弹
            current_price = self.crawler.get_latest_price(ticker)
            ipo_price = ipo_info.get("ipo_price")
            
            if current_price and ipo_price:
                if current_price < ipo_price * 0.95:  # 破发5%以上
                    window.signal = "pullback"
                elif current_price > ipo_price:  # 回到发行价之上
                    window.signal = "bounce"
        
        return window
    
    def _evaluate_base_breakout(self, ticker: str, ipo_info: Optional[dict]) -> IPOBaseBreakoutWindow:
        """评估IPO底部突破窗口."""
        window = IPOBaseBreakoutWindow(active=False, base_detected=False)
        
        if not ipo_info or not ipo_info.get("ipo_date"):
            return window
        
        try:
            # 获取历史数据
            from datetime import date
            bars = self.crawler.get_stock_bars(
                ticker,
                start=ipo_info["ipo_date"],
                end=date.today()
            )
            
            if len(bars) < 20:
                return window
            
            # 转换为DataFrame
            import pandas as pd
            df = pd.DataFrame([b.model_dump() for b in bars])
            
            # 检测底部形态
            base = self.pattern.base_detector.detect(df, ipo_info["ipo_date"])
            
            window.base_detected = base.has_base
            
            if base.has_base:
                window.active = True
                window.base_details = base
                
                # 检测突破
                breakout = self.pattern.breakout_scanner.scan(df, base)
                
                if breakout.breakout_detected:
                    window.breakout_signal = breakout.signal_strength
                elif breakout.pullback_entry:
                    window.breakout_signal = "pullback_entry"
            
            return window
            
        except Exception as e:
            self.logger.warning(f"Error evaluating base breakout for {ticker}: {e}")
            return window
    
    def _evaluate_lockup_expiry(self, ticker: str) -> LockupExpiryWindow:
        """评估禁售期到期窗口."""
        window = LockupExpiryWindow(active=False)
        
        try:
            lockup_info = self.lockup.get_lockup_info(ticker)
            
            if lockup_info and lockup_info.lockup_expiry_date:
                today = date.today()
                days_until = (lockup_info.lockup_expiry_date - today).days
                
                window.days_until = days_until
                window.supply_impact_pct = lockup_info.supply_impact_pct
                
                # 30天内算活跃窗口
                if days_until <= 30:
                    window.active = True
                
                # 状态判定
                if days_until < 0:
                    window.status = LockupStatus.EXPIRED
                elif days_until <= 3:
                    window.status = LockupStatus.IMMINENT
                elif days_until <= 14:
                    window.status = LockupStatus.WARNING
                else:
                    window.status = LockupStatus.ACTIVE
            
            return window
            
        except Exception as e:
            self.logger.warning(f"Error evaluating lockup for {ticker}: {e}")
            return window
    
    def _evaluate_first_earnings(self, ticker: str, ipo_info: Optional[dict]) -> FirstEarningsWindow:
        """评估首次财报窗口."""
        window = FirstEarningsWindow(active=False)
        
        try:
            # 获取下次财报日期
            next_date = self.earnings.get_next_earnings_date(ticker)
            
            if next_date and ipo_info and ipo_info.get("ipo_date"):
                days_since_ipo = (next_date - ipo_info["ipo_date"]).days
                
                # IPO后90-120天内的财报算首次财报
                if 60 <= days_since_ipo <= 150:
                    window.active = True
                    window.days_until = (next_date - date.today()).days
                    
                    # 获取财报信号
                    signal = self.earnings.analyze_earnings(ticker)
                    window.earnings_signal = signal
            
            return window
            
        except Exception as e:
            self.logger.warning(f"Error evaluating earnings for {ticker}: {e}")
            return window
    
    def _get_fundamental_score(self, ticker: str) -> float:
        """获取基本面评分."""
        try:
            score = self.screener.score_ipo(ticker)
            return float(score.total)
        except Exception:
            return 50.0  # 默认中性
    
    def _get_sentiment(self, ticker: str) -> SentimentResult:
        """获取情绪分析."""
        try:
            result = self.sentiment.analyze(ticker, days=7)
            return SentimentResult(
                ticker=ticker,
                overall_score=result.get("score", 0.0),
                buzz=result.get("buzz", "low"),
            )
        except Exception:
            return SentimentResult(ticker=ticker, overall_score=0.0)
    
    def _determine_overall_signal(
        self,
        windows: WindowsStatus,
        fundamental_score: float,
        sentiment: SentimentResult,
    ) -> tuple[OverallSignal, List[str]]:
        """判定综合信号.
        
        规则:
        - STRONG_OPPORTUNITY: 任一窗口强信号 + 基本面>=60 + 情绪>=0.3
        - OPPORTUNITY: 任一窗口有信号 + 基本面>=50
        - WATCH: 底部形成中 / 禁售期即将到期
        - NO_ACTION: 其他情况
        """
        reasons = []
        
        # 检查窗口信号
        has_strong_signal = False
        has_signal = False
        
        # 底部突破
        if windows.ipo_base_breakout.breakout_signal == "strong":
            has_strong_signal = True
            reasons.append("IPO底部强势突破确认")
        elif windows.ipo_base_breakout.breakout_signal in ["moderate", "weak"]:
            has_signal = True
            reasons.append("IPO底部突破信号")
        elif windows.ipo_base_breakout.breakout_signal == "pullback_entry":
            has_signal = True
            reasons.append("突破后回测入场机会")
        
        # 首日回调反弹
        if windows.first_day_pullback.signal == "bounce":
            has_signal = True
            reasons.append("首日回调后反弹")
        
        # 首次财报
        if windows.first_earnings.earnings_signal == "strong_buy":
            has_strong_signal = True
            reasons.append("首次财报超预期")
        elif windows.first_earnings.earnings_signal == "buy":
            has_signal = True
            reasons.append("首次财报积极")
        
        # 判定逻辑
        sentiment_score = float(sentiment.overall_score) if sentiment else 0.0
        
        if has_strong_signal and fundamental_score >= 60 and sentiment_score >= 0.3:
            return OverallSignal.STRONG_OPPORTUNITY, reasons
        
        if has_signal and fundamental_score >= 50:
            return OverallSignal.OPPORTUNITY, reasons
        
        # WATCH条件
        if windows.ipo_base_breakout.base_detected and not windows.ipo_base_breakout.breakout_signal:
            return OverallSignal.WATCH, ["底部形成中，等待突破"]
        
        if windows.lockup_expiry.days_until is not None and windows.lockup_expiry.days_until <= 14:
            return OverallSignal.WATCH, [f"禁售期{windows.lockup_expiry.days_until}天后到期"]
        
        if not reasons:
            reasons.append("暂无明显信号")
        
        return OverallSignal.NO_ACTION, reasons
    
    def _identify_risk_factors(self, windows: WindowsStatus, fundamental_score: float) -> List[str]:
        """识别风险因素."""
        risks = []
        
        # 基本面风险
        if fundamental_score < 40:
            risks.append("基本面评分较低")
        
        # 禁售期风险
        if windows.lockup_expiry.status in [LockupStatus.WARNING, LockupStatus.IMMINENT]:
            if windows.lockup_expiry.supply_impact_pct:
                risks.append(f"禁售期即将到期，解锁股份占流通股{windows.lockup_expiry.supply_impact_pct:.1%}")
        
        # 首日表现风险
        if windows.first_day_pullback.signal == "pullback":
            risks.append("IPO首日表现不佳，市场认可度存疑")
        
        # 财报风险
        if windows.first_earnings.days_until is not None and windows.first_earnings.days_until <= 7:
            risks.append("首次财报即将发布，不确定性较高")
        
        return risks


class CompositeScorer:
    """综合评分器 - 计算加权总分."""
    
    def __init__(self, aggregator: SignalAggregator):
        self.aggregator = aggregator
    
    def score(self, ticker: str) -> ScoreBreakdown:
        """对股票进行综合评分."""
        breakdown = ScoreBreakdown(ticker=ticker)
        
        # 基本面
        try:
            quick_score = self.aggregator.screener.score_ipo(ticker)
            breakdown.fundamental_score = float(quick_score.total)
        except Exception:
            pass
        
        # 形态
        try:
            report = self.aggregator.generate_report(ticker)
            if report.windows.ipo_base_breakout.breakout_signal == "strong":
                breakdown.pattern_score = 90.0
            elif report.windows.ipo_base_breakout.breakout_signal == "moderate":
                breakdown.pattern_score = 70.0
            elif report.windows.ipo_base_breakout.base_detected:
                breakdown.pattern_score = 50.0
        except Exception:
            pass
        
        # 情绪
        try:
            sentiment = self.aggregator.sentiment.analyze(ticker)
            score = sentiment.get("score", 0.0)
            breakdown.sentiment_score = (score + 1) * 50  # 转换-1~1到0~100
        except Exception:
            pass
        
        return breakdown
    
    def rank(self, tickers: List[str]) -> List[ScoreBreakdown]:
        """对多只股票排名."""
        results = [self.score(t) for t in tickers]
        return sorted(results, key=lambda s: s.total_score, reverse=True)
