"""情绪分析模块 - 分析市场对IPO的情绪倾向."""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from src.crawler.api import CrawlerAPI

logger = logging.getLogger(__name__)

# 正面关键词
POSITIVE_KEYWORDS = [
    "beat", "surpass", "exceed", "outperform", "strong", "solid", "robust",
    "growth", "profit", "upgrade", "raised guidance", "innovative", "breakthrough",
    "oversubscribed", "priced above range", "bullish", "buy", "outperform",
]

# 负面关键词
NEGATIVE_KEYWORDS = [
    "miss", "fall short", "underperform", "weak", "decline", "loss", "downgrade",
    "lowered guidance", "risk", "lawsuit", "dilution", "priced below range",
    "bearish", "sell", "underperform", "overvalued", "bubble",
]


class SentimentAnalyzer:
    """情绪分析器."""
    
    def __init__(
        self,
        crawler: Optional[CrawlerAPI] = None,
        use_ollama: bool = False,
    ):
        """初始化."""
        self.crawler = crawler or CrawlerAPI()
        self.use_ollama = use_ollama
        self.logger = logging.getLogger(__name__)
    
    def analyze(self, ticker: str, days: int = 7) -> dict:
        """分析情绪."""
        # 获取新闻
        news = self.crawler.get_news(ticker, days=days)
        
        if not news:
            return {
                "ticker": ticker,
                "score": 0.0,
                "sentiment": "neutral",
                "buzz": "low",
            }
        
        # 分析每条新闻
        scores = []
        for item in news:
            score = self._analyze_text(item.title + " " + (item.snippet or ""))
            scores.append(score)
        
        # 计算总体情绪
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        # 统计
        positive = sum(1 for s in scores if s > 0.2)
        negative = sum(1 for s in scores if s < -0.2)
        neutral = len(scores) - positive - negative
        
        # 判断情绪类型
        if avg_score > 0.3:
            sentiment = "bullish"
        elif avg_score < -0.3:
            sentiment = "bearish"
        else:
            sentiment = "neutral"
        
        # 计算热度
        daily_avg = len(news) / days
        if daily_avg > 10:
            buzz = "high"
        elif daily_avg > 3:
            buzz = "medium"
        else:
            buzz = "low"
        
        return {
            "ticker": ticker,
            "score": round(avg_score, 2),
            "sentiment": sentiment,
            "positive_count": positive,
            "negative_count": negative,
            "neutral_count": neutral,
            "buzz": buzz,
            "total_count": len(news),
        }
    
    def _analyze_text(self, text: str) -> float:
        """分析单条文本."""
        text_lower = text.lower()
        
        pos_count = sum(1 for word in POSITIVE_KEYWORDS if word in text_lower)
        neg_count = sum(1 for word in NEGATIVE_KEYWORDS if word in text_lower)
        
        if pos_count == 0 and neg_count == 0:
            return 0.0
        
        return (pos_count - neg_count) / (pos_count + neg_count + 1)


class SentimentTracker:
    """情绪追踪器 - 追踪情绪变化趋势."""
    
    def __init__(self, analyzer: SentimentAnalyzer):
        self.analyzer = analyzer
        self.history = {}
    
    def track(self, ticker: str) -> dict:
        """追踪情绪."""
        current = self.analyzer.analyze(ticker, days=7)
        
        # 获取历史记录
        if ticker in self.history:
            previous = self.history[ticker]
            change = current["score"] - previous["score"]
        else:
            change = 0.0
        
        # 保存历史
        self.history[ticker] = current
        
        current["change"] = round(change, 2)
        
        return current
