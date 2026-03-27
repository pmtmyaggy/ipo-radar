"""社交媒体爬虫 - 获取Reddit和StockTwits讨论数据.

PRD 3.4
"""

import logging
import os
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import requests

from .base import BaseCrawler
from .models.schemas import SocialPost

logger = logging.getLogger(__name__)


class RedditCrawler(BaseCrawler):
    """Reddit API爬虫.

    获取r/stocks, r/wallstreetbets等子版块关于IPO的讨论。
    使用Reddit的OAuth API或JSON API。
    """

    SUBREDDIT_URL = "https://www.reddit.com/r/{subreddit}/search.json"
    DEFAULT_SUBREDDITS = ["stocks", "wallstreetbets", "investing", "IPOs"]

    def __init__(self, db_manager: Any = None) -> None:
        super().__init__(
            name="reddit",
            rate_limit=2.0,  # 30次/分钟（保守）
            db_manager=db_manager,
        )
        self.subreddits = self.DEFAULT_SUBREDDITS
        self.client_id = os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.user_agent = os.getenv("REDDIT_USER_AGENT", "IPO-Radar:v1.0 (by /u/IPO-Radar)")
        self.access_token = None
        self.token_expiry = datetime.min
        
        # 如果提供了凭证，尝试获取Token
        if self.client_id and self.client_secret:
            self._authenticate()

    def _authenticate(self) -> None:
        """获取Reddit OAuth Token."""
        try:
            auth = requests.auth.HTTPBasicAuth(self.client_id, self.client_secret)
            data = {"grant_type": "client_credentials"}
            headers = {"User-Agent": self.user_agent}
            response = requests.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=auth, data=data, headers=headers, timeout=10
            )
            response.raise_for_status()
            res_data = response.json()
            self.access_token = res_data.get("access_token")
            # 通常有效期1小时
            self.token_expiry = datetime.now() + timedelta(seconds=res_data.get("expires_in", 3600) - 60)
            logger.info("Successfully authenticated with Reddit API")
        except Exception as e:
            logger.warning(f"Failed to authenticate with Reddit API: {e}")

    def fetch(self, **kwargs: Any) -> list[SocialPost]:
        """获取Reddit帖子."""
        ticker = kwargs.get("ticker")
        company_name = kwargs.get("company_name", "")
        days = kwargs.get("days", 7)
        subreddits = kwargs.get("subreddits", self.subreddits)
        limit = kwargs.get("limit", 25)

        if ticker:
            query = f"{ticker} {company_name} IPO".strip()
        else:
            query = "IPO"

        all_posts = []
        cutoff_date = datetime.now() - timedelta(days=days)

        for subreddit in subreddits:
            try:
                posts = self._fetch_subreddit(
                    subreddit, query, limit, cutoff_date, ticker=ticker
                )
                all_posts.extend(posts)
            except Exception as e:
                logger.warning(f"Failed to fetch from r/{subreddit}: {e}")

        # 去重（基于URL）
        seen_urls = set()
        unique_posts = []
        for post in all_posts:
            if getattr(post, 'url', None) not in seen_urls:
                # 简单存储 url (由于 schema 设计，此处作为信息记录，原实现在 NewsItem 中)
                seen_urls.add(getattr(post, 'url', None))
                unique_posts.append(post)

        return unique_posts

    def _fetch_subreddit(
        self, subreddit: str, query: str, limit: int, cutoff_date: datetime, ticker: str | None = None
    ) -> list[SocialPost]:
        """从指定子版块获取帖子."""
        # 如果 token 过期且配置了凭证，重新获取
        if self.client_id and datetime.now() >= self.token_expiry:
            self._authenticate()

        # 使用 OAuth 端点或回退到 JSON 端点
        if self.access_token:
            url = f"https://oauth.reddit.com/r/{subreddit}/search"
            headers = {
                "Authorization": f"bearer {self.access_token}",
                "User-Agent": self.user_agent
            }
        else:
            url = self.SUBREDDIT_URL.format(subreddit=subreddit)
            headers = {"User-Agent": self.user_agent}

        params = {
            "q": query,
            "sort": "new",
            "limit": limit,
            "restrict_sr": "on",
            "t": "week" if (datetime.now() - cutoff_date).days <= 7 else "month",
        }

        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()
        posts = []

        for child in data.get("data", {}).get("children", []):
            try:
                post_data = child.get("data", {})
                created_utc = post_data.get("created_utc")
                if created_utc:
                    published_at = datetime.fromtimestamp(created_utc)
                    if published_at < cutoff_date:
                        continue
                else:
                    published_at = datetime.now()

                title = post_data.get("title", "")
                selftext = post_data.get("selftext", "")[:500]
                author = post_data.get("author", "unknown")
                score = post_data.get("score", 0)
                num_comments = post_data.get("num_comments", 0)

                mentioned_tickers = self._extract_tickers(title + " " + selftext)
                detected_ticker = mentioned_tickers[0] if mentioned_tickers else ticker

                if not detected_ticker:
                    continue

                post = SocialPost(
                    ticker=detected_ticker,
                    platform=f"reddit/r/{subreddit}",
                    title=title,
                    body=selftext,
                    author=author,
                    score=score,
                    num_comments=num_comments,
                    created_at=published_at,
                    sentiment_score=None
                )
                # 记录 url 供去重使用
                permalink = post_data.get("permalink", "")
                setattr(post, 'url', f"https://www.reddit.com{permalink}" if permalink else post_data.get("url", ""))
                
                posts.append(post)

            except Exception as e:
                logger.debug(f"Error parsing Reddit post: {e}")
                continue

        return posts

    def _extract_tickers(self, text: str) -> list[str]:
        """从文本中提取可能的股票代码."""
        ticker_pattern = r"\$([A-Z]{1,5})\b"
        return re.findall(ticker_pattern, text)


class StockTwitsCrawler(BaseCrawler):
    """StockTwits API 爬虫."""

    def __init__(self, db_manager: Any = None) -> None:
        super().__init__(
            name="stocktwits",
            rate_limit=1.0,  # StockTwits limits: ~200/hour per IP
            db_manager=db_manager,
        )

    def fetch(self, **kwargs: Any) -> list[SocialPost]:
        ticker = kwargs.get("ticker")
        if not ticker:
            return []

        url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            posts = []
            for msg in data.get("messages", []):
                try:
                    created_at_str = msg.get("created_at")
                    if created_at_str:
                        published_at = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ")
                    else:
                        published_at = datetime.now()
                        
                    body = msg.get("body", "")
                    user = msg.get("user", {})
                    author = user.get("username", "unknown")
                    
                    # 情绪标签
                    sentiment_str = (msg.get("entities", {}).get("sentiment") or {}).get("basic", "")
                    sentiment_score = 0.8 if sentiment_str == "Bullish" else -0.8 if sentiment_str == "Bearish" else 0.0

                    posts.append(SocialPost(
                        ticker=ticker.upper(),
                        platform="stocktwits",
                        title=None,
                        body=body,
                        author=author,
                        score=msg.get("likes", {}).get("total", 0),
                        num_comments=0,
                        created_at=published_at,
                        sentiment_score=Decimal(str(sentiment_score))
                    ))
                except Exception as e:
                    logger.debug(f"Error parsing Stocktwits post: {e}")
                    continue
            return posts

        except Exception as e:
            logger.error(f"Error fetching Stocktwits data for {ticker}: {e}")
            return []


class SocialFetcherAggregator:
    """聚合 Reddit 和 StockTwits 的数据."""
    
    def __init__(self, db_manager: Any = None):
        self.reddit = RedditCrawler(db_manager)
        self.stocktwits = StockTwitsCrawler(db_manager)
        
    def fetch(self, ticker: str, days: int = 7) -> list[SocialPost]:
        posts = []
        posts.extend(self.reddit.fetch(ticker=ticker, days=days))
        posts.extend(self.stocktwits.fetch(ticker=ticker))
        return posts
