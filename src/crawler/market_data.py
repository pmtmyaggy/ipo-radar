"""行情数据爬虫 - 使用yfinance获取股票数据."""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from typing import Optional

import pandas as pd
import yfinance as yf

from .base import BaseCrawler
from .models.schemas import StockBar

logger = logging.getLogger(__name__)


class MarketDataCrawler(BaseCrawler):
    """行情数据爬虫.

    使用yfinance获取股票历史价格和实时数据。
    """

    def __init__(self, db_manager: Any = None):
        super().__init__(
            name="market_data",
            rate_limit=2.0,  # yfinance限制较宽松
            db_manager=db_manager,
        )

    def fetch(self, **kwargs: Any) -> list[StockBar]:
        """获取行情数据.

        Args:
            ticker: 股票代码
            start: 开始日期
            end: 结束日期
        """
        ticker = kwargs.get("ticker")
        start = kwargs.get("start")
        end = kwargs.get("end", date.today())

        if not ticker:
            return []

        try:
            yf_ticker = yf.Ticker(ticker)
            hist = yf_ticker.history(start=start, end=end)

            bars: list[StockBar] = []
            for idx, row in hist.iterrows():
                bar = StockBar(
                    ticker=ticker,
                    date=idx.date(),
                    open=Decimal(str(round(float(row["Open"]), 2))),
                    high=Decimal(str(round(float(row["High"]), 2))),
                    low=Decimal(str(round(float(row["Low"]), 2))),
                    close=Decimal(str(round(float(row["Close"]), 2))),
                    volume=int(row["Volume"]),
                )
                bars.append(bar)

            return bars

        except Exception as e:
            logger.error(f"Failed to fetch market data for {ticker}: {e}")
            return []

    def get_latest_price(self, ticker: str) -> Optional[float]:
        """获取最新价格."""
        try:
            yf_ticker = yf.Ticker(ticker)
            info = yf_ticker.info
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            return float(price) if price is not None else None
        except Exception as e:
            logger.error(f"Failed to get latest price for {ticker}: {e}")
            return None

    def backfill_history(self, ticker: str, ipo_date: date) -> list[StockBar]:
        """回填IPO以来的所有历史数据."""
        return self.fetch(ticker=ticker, start=ipo_date)


class IntradaySnapshotCrawler(BaseCrawler):
    """盘中快照爬虫.

    用于实时价格监控和突破检测。
    """

    def __init__(self, db_manager: Any = None):
        super().__init__(
            name="intraday_snapshot",
            rate_limit=4.0,  # 每15分钟可以运行一次
            db_manager=db_manager,
        )

    def fetch(self, **kwargs: Any) -> dict[str, dict[str, Any]]:
        """获取当前价格快照.

        Args:
            tickers: 股票代码列表
        """
        tickers = kwargs.get("tickers", [])

        snapshots: dict[str, dict[str, Any]] = {}
        for ticker in tickers:
            try:
                yf_ticker = yf.Ticker(ticker)
                info = yf_ticker.info

                snapshots[ticker] = {
                    "price": info.get("regularMarketPrice"),
                    "change": info.get("regularMarketChange"),
                    "change_pct": info.get("regularMarketChangePercent"),
                    "volume": info.get("regularMarketVolume"),
                    "timestamp": datetime.now(),
                }
            except Exception as e:
                logger.warning(f"Failed to get snapshot for {ticker}: {e}")
                continue

        return snapshots
