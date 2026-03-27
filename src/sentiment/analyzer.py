"""情绪分析模块 - 分析市场对IPO的情绪倾向.

支持多种分析方式:
1. 关键词匹配 (默认，无需配置)
2. OpenAI API (包括官方和兼容平台)
3. Ollama 本地模型
"""

import json
import logging
import os
from typing import Any, Optional, TypedDict, cast

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


class LLMClient:
    """LLM 客户端 - 支持 OpenAI 协议的所有平台."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """初始化 LLM 客户端.
        
        Args:
            api_key: API Key，默认从 OPENAI_API_KEY 环境变量读取
            base_url: API 基础 URL，默认从 OPENAI_BASE_URL 读取
            model: 模型名称，默认从 OPENAI_MODEL 读取
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model: str = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        self.client = None
        
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
                logger.info(f"LLM client initialized: {self.base_url}, model: {self.model}")
            except ImportError:
                logger.warning("openai package not installed, LLM analysis disabled")
            except Exception as e:
                logger.error(f"Failed to initialize LLM client: {e}")
    
    def is_available(self) -> bool:
        """检查 LLM 是否可用."""
        return self.client is not None
    
    def analyze_sentiment(self, text: str) -> dict[str, str | float]:
        """使用 LLM 分析情绪.
        
        Args:
            text: 待分析的文本
            
        Returns:
            {"sentiment": "bullish/neutral/bearish", "score": float, "reasoning": str}
        """
        if not self.client:
            return {"sentiment": "neutral", "score": 0.0, "reasoning": "LLM not available"}
        
        try:
            prompt = f"""Analyze the sentiment of the following text about an IPO stock.
Text: "{text}"

Respond in JSON format:
{{
    "sentiment": "bullish" or "neutral" or "bearish",
    "score": float between -1.0 (very bearish) and 1.0 (very bullish),
    "reasoning": brief explanation in Chinese (50 words max)
}}

Rules:
- bullish = positive outlook, strong fundamentals, oversubscribed, priced above range
- bearish = negative outlook, weak fundamentals, risks, lawsuits, overvalued
- neutral = mixed signals or no clear sentiment"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a financial sentiment analyst. Respond only in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200,
            )
            
            # 处理不同的响应格式
            if hasattr(response, 'choices') and response.choices:
                content = (response.choices[0].message.content or "").strip()
            elif isinstance(response, dict):
                content = response.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            elif isinstance(response, str):
                content = response.strip()
            else:
                content = str(response)
            
            logger.debug(f"LLM raw response: {content[:200]}")
            
            # 提取 JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            # 验证并返回
            return {
                "sentiment": result.get("sentiment", "neutral"),
                "score": max(-1.0, min(1.0, float(result.get("score", 0)))),
                "reasoning": result.get("reasoning", ""),
            }
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}, response type: {type(response)}")
            return {"sentiment": "neutral", "score": 0.0, "reasoning": f"Error: {str(e)[:50]}"}


class SentimentAnalysisResult(TypedDict, total=False):
    """情绪分析结果字典."""

    ticker: str
    score: float
    sentiment: str
    positive_count: int
    negative_count: int
    neutral_count: int
    buzz: str
    total_count: int
    method: str
    sample_reasoning: str
    change: float


class SentimentAnalyzer:
    """情绪分析器 - 支持关键词和 LLM 两种分析方式."""
    
    def __init__(
        self,
        crawler: Optional[CrawlerAPI] = None,
        use_llm: bool = True,
        use_ollama: bool = False,
    ) -> None:
        """初始化.
        
        Args:
            crawler: 爬虫 API 实例
            use_llm: 是否使用 LLM 分析（需要配置 API Key）
            use_ollama: 是否使用本地 Ollama 模型
        """
        self.crawler = crawler or CrawlerAPI()
        self.use_llm = use_llm and not use_ollama
        self.use_ollama = use_ollama
        self.logger = logging.getLogger(__name__)
        
        # 初始化 LLM 客户端
        self.llm_client = LLMClient() if use_llm else None
        
        if self.llm_client and self.llm_client.is_available():
            self.logger.info("LLM sentiment analysis enabled")
        else:
            self.logger.info("Using keyword-based sentiment analysis")
    
    def analyze(self, ticker: str, days: int = 7) -> SentimentAnalysisResult:
        """分析情绪.
        
        Args:
            ticker: 股票代码
            days: 分析最近几天的数据
            
        Returns:
            情绪分析结果字典
        """
        # 获取新闻
        news = self.crawler.get_news(ticker, days=days)
        
        if not news:
            return {
                "ticker": ticker,
                "score": 0.0,
                "sentiment": "neutral",
                "buzz": "low",
                "method": "none",
            }
        
        # 分析每条新闻
        scores: list[float] = []
        llm_results: list[dict[str, str | float]] = []
        
        for item in news:
            text = item.title + " " + (item.snippet or "")
            
            # 优先使用 LLM 分析
            if self.llm_client and self.llm_client.is_available():
                llm_result = self.llm_client.analyze_sentiment(text)
                scores.append(float(llm_result["score"]))
                llm_results.append(llm_result)
            else:
                # 使用关键词分析
                score = self._analyze_text(text)
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
        
        result: SentimentAnalysisResult = {
            "ticker": ticker,
            "score": round(avg_score, 2),
            "sentiment": sentiment,
            "positive_count": positive,
            "negative_count": negative,
            "neutral_count": neutral,
            "buzz": buzz,
            "total_count": len(news),
            "method": "llm" if (self.llm_client and self.llm_client.is_available()) else "keyword",
        }
        
        # 如果有 LLM 分析，添加推理信息
        if llm_results:
            result["sample_reasoning"] = str(llm_results[0].get("reasoning", ""))
        
        return result
    
    def _analyze_text(self, text: str) -> float:
        """分析单条文本（关键词方式）."""
        text_lower = text.lower()
        
        pos_count = sum(1 for word in POSITIVE_KEYWORDS if word in text_lower)
        neg_count = sum(1 for word in NEGATIVE_KEYWORDS if word in text_lower)
        
        if pos_count == 0 and neg_count == 0:
            return 0.0
        
        return (pos_count - neg_count) / (pos_count + neg_count + 1)


class SentimentTracker:
    """情绪追踪器 - 追踪情绪变化趋势."""
    
    def __init__(self, analyzer: Optional[SentimentAnalyzer] = None) -> None:
        self.analyzer = analyzer or SentimentAnalyzer()
        self.history: dict[str, SentimentAnalysisResult] = {}
    
    def track(self, ticker: str) -> SentimentAnalysisResult:
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
