"""情绪分析模块测试."""

import pytest
from src.sentiment.analyzer import SentimentAnalyzer


class TestSentimentAnalyzer:
    """测试情绪分析器."""

    def test_analyzer_creation(self):
        """测试分析器创建."""
        analyzer = SentimentAnalyzer()
        assert analyzer is not None
        assert hasattr(analyzer, 'crawler')

    def test_analyze_returns_dict(self):
        """测试返回字典格式."""
        analyzer = SentimentAnalyzer()
        result = analyzer.analyze("TEST", days=7)
        
        assert isinstance(result, dict)
        assert "score" in result
        assert "buzz" in result


class TestSentimentTracker:
    """测试情绪追踪器."""

    def test_tracker_creation(self):
        """测试追踪器创建."""
        from src.sentiment.analyzer import SentimentTracker, SentimentAnalyzer
        analyzer = SentimentAnalyzer()
        tracker = SentimentTracker(analyzer)
        assert tracker is not None
