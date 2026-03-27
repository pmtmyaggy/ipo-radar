"""新闻爬虫 - 从Google News RSS获取IPO相关新闻."""

import logging
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import quote

import feedparser
import requests

from .base import BaseCrawler
from .models.schemas import NewsItem

logger = logging.getLogger(__name__)


class GoogleNewsCrawler(BaseCrawler):
    """Google News RSS爬虫.

    通过RSS获取股票相关新闻。
    """

    RSS_URL = "https://news.google.com/rss/search"

    def __init__(self, db_manager: Any = None) -> None:
        super().__init__(
            name="google_news",
            rate_limit=0.2,  # 每5秒1次
            db_manager=db_manager,
        )

    def fetch(self, **kwargs: Any) -> list[NewsItem]:
        """获取新闻.

        Args:
            ticker: 股票代码
            company_name: 公司名称
            days: 获取过去多少天的新闻
        """
        ticker = kwargs.get("ticker")
        company_name = kwargs.get("company_name", "")
        days = kwargs.get("days", 7)

        if not ticker:
            return []

        # 构建搜索查询
        query = f"{ticker} {company_name} IPO".strip()
        encoded_query = quote(query)

        url = f"{self.RSS_URL}?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

        try:
            feed = feedparser.parse(url)

            news_items = []
            cutoff_date = datetime.now() - timedelta(days=days)

            for entry in feed.entries:
                try:
                    published = self._parse_date(entry.get("published", ""))

                    # 过滤旧新闻
                    if published and published < cutoff_date:
                        continue

                    news = NewsItem(
                        ticker=ticker,
                        title=entry.get("title", ""),
                        source=entry.get("source", {}).get("title", "Unknown"),
                        published_at=published or datetime.now(),
                        url=entry.get("link", ""),
                        snippet=self._clean_html(entry.get("summary", "")),
                    )

                    news_items.append(news)

                except Exception as e:
                    logger.warning(f"Failed to parse news entry: {e}")
                    continue

            return news_items

        except Exception as e:
            logger.error(f"Failed to fetch news for {ticker}: {e}")
            return []

    def _parse_date(self, date_str: str) -> datetime | None:
        """解析日期字符串."""
        formats = [
            "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def _clean_html(self, html: str) -> str:
        """清理HTML标签."""
        clean = re.sub(r"<[^>]+>", "", html)
        return clean[:500]  # 限制长度


