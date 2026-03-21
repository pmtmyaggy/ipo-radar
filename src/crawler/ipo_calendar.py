"""IPO日历爬虫 - 从多个数据源获取IPO信息.

支持的数据源：
- Nasdaq IPO Calendar API (主要)
- SEC EDGAR EFTS (主要)
- IPOScoop (备用)
"""

import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import requests

from .base import BaseCrawler
from .models.schemas import IPOEvent, IPOStatus

logger = logging.getLogger(__name__)


class NasdaqIPOCalendarCrawler(BaseCrawler):
    """Nasdaq IPO日历爬虫.
    
    从 Nasdaq API 获取即将上市和近期上市的IPO信息。
    
    API端点: https://api.nasdaq.com/api/ipo/calendar
    """
    
    BASE_URL = "https://api.nasdaq.com/api/ipo/calendar"
    
    def __init__(self, db_manager=None):
        """初始化Nasdaq爬虫."""
        super().__init__(
            name="nasdaq_ipo_calendar",
            rate_limit=1.0,  # 每秒1个请求
            db_manager=db_manager,
        )
    
    def fetch(self, **kwargs) -> list[IPOEvent]:
        """获取IPO日历数据.
        
        Args:
            **kwargs: 可选参数
                - upcoming: 是否获取即将上市的IPO，默认True
                - priced: 是否获取已定价的IPO，默认True
                - filed: 是否获取已提交的IPO，默认False
        
        Returns:
            IPOEvent列表
        """
        events = []
        
        try:
            # 获取即将上市的IPO
            if kwargs.get("upcoming", True):
                upcoming = self._fetch_upcoming()
                events.extend(upcoming)
            
            # 获取已定价的IPO
            if kwargs.get("priced", True):
                priced = self._fetch_priced()
                events.extend(priced)
            
            # 获取已提交的IPO
            if kwargs.get("filed", False):
                filed = self._fetch_filed()
                events.extend(filed)
            
            logger.info(f"Fetched {len(events)} IPO events from Nasdaq")
            return events
            
        except Exception as e:
            logger.error(f"Error fetching from Nasdaq: {e}")
            return []
    
    def fetch_upcoming(self, days: int = 30) -> list[IPOEvent]:
        """获取即将上市的IPO.
        
        Args:
            days: 获取未来多少天的IPO，默认30天
        
        Returns:
            IPOEvent列表
        """
        return self._fetch_upcoming()
    
    def _fetch_upcoming(self) -> list[IPOEvent]:
        """获取即将上市的IPO."""
        url = f"{self.BASE_URL}?type=upcoming"
        
        try:
            response = self._request(
                url,
                user_agent_type="browser",  # Nasdaq需要浏览器User-Agent
            )
            response.raise_for_status()
            
            data = response.json()
            return self._parse_response(data, IPOStatus.FILED)
            
        except Exception as e:
            logger.error(f"Failed to fetch upcoming IPOs from Nasdaq: {e}")
            return []
    
    def _fetch_priced(self) -> list[IPOEvent]:
        """获取已定价的IPO."""
        url = f"{self.BASE_URL}?type=priced"
        
        try:
            response = self._request(
                url,
                user_agent_type="browser",
            )
            response.raise_for_status()
            
            data = response.json()
            return self._parse_response(data, IPOStatus.TRADING)
            
        except Exception as e:
            logger.error(f"Failed to fetch priced IPOs from Nasdaq: {e}")
            return []
    
    def _fetch_filed(self) -> list[IPOEvent]:
        """获取已提交的IPO（S-1文件）."""
        url = f"{self.BASE_URL}?type=filed"
        
        try:
            response = self._request(
                url,
                user_agent_type="browser",
            )
            response.raise_for_status()
            
            data = response.json()
            return self._parse_response(data, IPOStatus.FILED)
            
        except Exception as e:
            logger.error(f"Failed to fetch filed IPOs from Nasdaq: {e}")
            return []
    
    def _parse_response(self, data: dict, default_status: IPOStatus) -> list[IPOEvent]:
        """解析Nasdaq API响应.
        
        Args:
            data: API响应JSON
            default_status: 默认IPO状态
        
        Returns:
            IPOEvent列表
        """
        events = []
        
        try:
            # Nasdaq API结构: data -> upcoming/priced/filed -> rows
            if "data" not in data:
                logger.warning("No 'data' field in Nasdaq response")
                return []
            
            # 获取第一个非空的数据类型
            ipo_data = None
            for key in ["upcoming", "priced", "filed"]:
                if key in data["data"] and data["data"][key]:
                    ipo_data = data["data"][key]
                    break
            
            if not ipo_data:
                logger.warning("No IPO data found in Nasdaq response")
                return []
            
            rows = ipo_data.get("rows", [])
            
            for row in rows:
                try:
                    event = self._parse_row(row, default_status)
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.warning(f"Failed to parse row: {row}, error: {e}")
                    continue
            
            return events
            
        except Exception as e:
            logger.error(f"Error parsing Nasdaq response: {e}")
            return []
    
    def _parse_row(self, row: dict, default_status: IPOStatus) -> Optional[IPOEvent]:
        """解析单行数据为IPOEvent.
        
        Args:
            row: 单行数据字典
            default_status: 默认状态
        
        Returns:
            IPOEvent或None
        """
        try:
            # 提取股票代码
            ticker = row.get("proposedTickerSymbol") or row.get("symbol")
            if ticker:
                ticker = ticker.strip().upper()
            
            # 提取公司名称
            company_name = row.get("companyName") or row.get("name", "")
            
            # 提取交易所
            exchange = row.get("proposedExchange") or row.get("exchange")
            
            # 提取预计上市日期
            expected_date = None
            date_str = row.get("expectedPricedDate") or row.get("pricedDate")
            if date_str:
                try:
                    # 尝试多种日期格式
                    for fmt in ["%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"]:
                        try:
                            expected_date = datetime.strptime(date_str, fmt).date()
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass
            
            # 提取价格区间
            price_range_low = None
            price_range_high = None
            
            price_range = row.get("proposedSharePrice") or row.get("priceRange")
            if price_range and price_range != "N/A":
                try:
                    # 处理 "$15.00 - $18.00" 格式
                    if "-" in price_range:
                        parts = price_range.replace("$", "").split("-")
                        price_range_low = float(parts[0].strip())
                        price_range_high = float(parts[1].strip())
                    else:
                        # 单一价格
                        price = float(price_range.replace("$", "").strip())
                        price_range_low = price
                        price_range_high = price
                except (ValueError, IndexError):
                    pass
            
            # 提取最终价格（已定价的IPO）
            final_price = None
            price_str = row.get("price")
            if price_str and price_str != "N/A":
                try:
                    final_price = float(price_str.replace("$", "").strip())
                except ValueError:
                    pass
            
            # 提取发行股数
            shares_offered = None
            shares_str = row.get("sharesOffered")
            if shares_str and shares_str != "N/A":
                try:
                    # 处理 "10,000,000" 格式
                    shares_offered = int(shares_str.replace(",", "").strip())
                except ValueError:
                    pass
            
            # 提取发行规模
            deal_size_mm = None
            deal_str = row.get("dealSize") or row.get("proposedMarketCap")
            if deal_str and deal_str != "N/A":
                try:
                    # 处理 "$150.0 M" 或 "$150.0" 格式
                    deal_str = deal_str.replace("$", "").replace(",", "").strip()
                    if "M" in deal_str:
                        deal_size_mm = float(deal_str.replace("M", "").strip())
                    elif "B" in deal_str:
                        deal_size_mm = float(deal_str.replace("B", "").strip()) * 1000
                    else:
                        deal_size_mm = float(deal_str) / 1_000_000
                except ValueError:
                    pass
            
            # 提取主承销商
            lead_underwriter = row.get("leadManagers") or row.get("underwriters")
            
            # 提取行业
            sector = row.get("sector")
            
            # 确定状态
            status = default_status
            if final_price:
                status = IPOStatus.PRICED
            
            # 创建IPOEvent
            event = IPOEvent(
                ticker=ticker,
                company_name=company_name,
                exchange=exchange,
                expected_date=expected_date,
                price_range_low=price_range_low,
                price_range_high=price_range_high,
                final_price=final_price,
                shares_offered=shares_offered,
                deal_size_mm=deal_size_mm,
                lead_underwriter=lead_underwriter,
                status=status,
                sector=sector,
            )
            
            return event
            
        except Exception as e:
            logger.warning(f"Error parsing row: {e}")
            return None


class IPOScoopCrawler(BaseCrawler):
    """IPOScoop备用爬虫.
    
    当Nasdaq API不可用时，作为备用数据源。
    使用HTML解析获取IPO日历。
    
    URL: https://www.iposcoop.com/ipo-calendar/
    """
    
    BASE_URL = "https://www.iposcoop.com/ipo-calendar/"
    
    def __init__(self, db_manager=None):
        """初始化IPOScoop爬虫."""
        super().__init__(
            name="iposcoop_calendar",
            rate_limit=0.2,  # 每5秒1个请求（保守）
            db_manager=db_manager,
        )
    
    def fetch(self, **kwargs) -> list[IPOEvent]:
        """获取IPO日历（备用）."""
        try:
            response = self._request(
                self.BASE_URL,
                user_agent_type="browser",
            )
            response.raise_for_status()
            
            soup = self._parse_html(response.text)
            return self._parse_calendar(soup)
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch from IPOScoop: {e}")
            return []
    
    def _parse_calendar(self, soup) -> list[IPOEvent]:
        """解析IPO日历页面."""
        events = []
        
        # TODO: 实现HTML解析逻辑
        # IPOScoop页面结构较复杂，需要解析表格
        logger.warning("IPOScoop parser not fully implemented")
        
        return events


class IPOCalendarAggregator:
    """IPO日历聚合器.
    
    协调多个数据源，提供统一的IPO日历接口。
    优先使用Nasdaq，失败时回退到IPOScoop。
    """
    
    def __init__(self, db_manager=None):
        """初始化聚合器."""
        self.nasdaq = NasdaqIPOCalendarCrawler(db_manager)
        self.iposcoop = IPOScoopCrawler(db_manager)
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
    
    def fetch_all(self, **kwargs) -> list[IPOEvent]:
        """从所有可用源获取IPO日历.
        
        优先顺序：Nasdaq -> IPOScoop
        
        Returns:
            合并后的IPOEvent列表（去重）
        """
        all_events = []
        
        # 尝试Nasdaq
        try:
            nasdaq_events = self.nasdaq.fetch(**kwargs)
            if nasdaq_events:
                all_events.extend(nasdaq_events)
                self.logger.info(f"Got {len(nasdaq_events)} events from Nasdaq")
        except Exception as e:
            self.logger.warning(f"Nasdaq fetch failed: {e}")
        
        # 如果Nasdaq失败或数据不足，尝试IPOScoop
        if len(all_events) < 5:
            try:
                iposcoop_events = self.iposcoop.fetch(**kwargs)
                if iposcoop_events:
                    all_events.extend(iposcoop_events)
                    self.logger.info(f"Got {len(iposcoop_events)} events from IPOScoop")
            except Exception as e:
                self.logger.warning(f"IPOScoop fetch failed: {e}")
        
        # 去重（基于ticker + expected_date）
        unique_events = self._deduplicate(all_events)
        
        return unique_events
    
    def _deduplicate(self, events: list[IPOEvent]) -> list[IPOEvent]:
        """去重IPO事件.
        
        基于ticker和expected_date进行去重。
        
        Args:
            events: IPOEvent列表
        
        Returns:
            去重后的列表
        """
        seen = set()
        unique = []
        
        for event in events:
            key = (event.ticker, event.expected_date)
            if key not in seen:
                seen.add(key)
                unique.append(event)
        
        return unique
    
    def get_upcoming_ipos(self, days: int = 30) -> list[IPOEvent]:
        """获取即将上市的IPO.
        
        Args:
            days: 未来多少天，默认30
        
        Returns:
            过滤后的IPOEvent列表
        """
        events = self.fetch_all(upcoming=True, priced=False, filed=False)
        
        # 过滤日期
        today = date.today()
        cutoff = today + timedelta(days=days)
        
        filtered = [
            e for e in events
            if e.expected_date and today <= e.expected_date <= cutoff
        ]
        
        # 按日期排序
        filtered.sort(key=lambda x: x.expected_date or date.max)
        
        return filtered
    
    def get_recent_ipos(self, days: int = 90) -> list[IPOEvent]:
        """获取近期上市的IPO.
        
        Args:
            days: 过去多少天，默认90
        
        Returns:
            过滤后的IPOEvent列表
        """
        events = self.fetch_all(upcoming=False, priced=True, filed=False)
        
        # 过滤日期
        today = date.today()
        cutoff = today - timedelta(days=days)
        
        filtered = [
            e for e in events
            if e.expected_date and cutoff <= e.expected_date <= today
        ]
        
        # 按日期倒序
        filtered.sort(key=lambda x: x.expected_date or date.min, reverse=True)
        
        return filtered
