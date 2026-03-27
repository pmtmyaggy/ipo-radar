"""IPO日历爬虫 - 从多个数据源获取IPO信息.

支持的数据源：
- Nasdaq IPO Calendar API (主要)
- SEC EDGAR EFTS (主要)
- IPOScoop (备用)
"""

import json
import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
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

    def __init__(self, db_manager: Any = None):
        """初始化Nasdaq爬虫."""
        super().__init__(
            name="nasdaq_ipo_calendar",
            rate_limit=1.0,  # 每秒1个请求
            db_manager=db_manager,
        )

    def fetch(self, **kwargs: Any) -> list[IPOEvent]:
        """获取IPO日历数据.

        Args:
            **kwargs: 可选参数
                - upcoming: 是否获取即将上市的IPO，默认True
                - priced: 是否获取已定价的IPO，默认True
                - filed: 是否获取已提交的IPO，默认False

        Returns:
            IPOEvent列表
        """
        try:
            # Nasdaq API 返回所有数据，不需要分类型请求
            response = self._request(
                self.BASE_URL,
                user_agent_type="browser",
            )
            response.raise_for_status()

            data = response.json()
            all_events = self._parse_response(data, IPOStatus.FILED)

            # 根据 kwargs 过滤
            events = []
            want_upcoming = kwargs.get("upcoming", True)
            want_priced = kwargs.get("priced", True)
            want_filed = kwargs.get("filed", False)

            for event in all_events:
                # 根据事件状态过滤
                if event.status == IPOStatus.FILED and want_upcoming:
                    events.append(event)
                elif event.status == IPOStatus.PRICED and want_priced:
                    events.append(event)
                elif event.status == IPOStatus.TRADING and want_priced:
                    events.append(event)
                elif event.status == IPOStatus.FILED and want_filed:
                    events.append(event)

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

            # 处理不同类型的数据结构
            # upcoming: {'upcomingTable': {'rows': [...]}}
            # priced/filed: {'rows': [...]}
            rows = []

            for key in ["upcoming", "priced", "filed"]:
                if key in data["data"] and data["data"][key]:
                    ipo_data = data["data"][key]

                    # upcoming 有嵌套结构
                    if key == "upcoming" and "upcomingTable" in ipo_data:
                        table_rows = ipo_data["upcomingTable"].get("rows", [])
                        rows.extend(table_rows)
                    else:
                        # priced/filed 直接有 rows
                        table_rows = ipo_data.get("rows", [])
                        rows.extend(table_rows)

            if not rows:
                logger.warning("No IPO rows found in Nasdaq response")
                return []

            for row in rows:
                try:
                    event = self._parse_row(row, default_status)
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.warning(f"Failed to parse row: {row}, error: {e}")
                    continue

            logger.info(f"Parsed {len(events)} IPO events from Nasdaq")
            return events

        except Exception as e:
            logger.error(f"Error parsing Nasdaq response: {e}")
            return []

    def _parse_row(self, row: dict[str, Any], default_status: IPOStatus) -> Optional[IPOEvent]:
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
            date_str = (
                row.get("expectedPriceDate")
                or row.get("expectedPricedDate")
                or row.get("pricedDate")
            )
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
            price_range_low: Decimal | None = None
            price_range_high: Decimal | None = None

            price_range = row.get("proposedSharePrice") or row.get("priceRange")
            if price_range and price_range.strip().upper() not in ("N/A", "TBD", "", "-"):
                try:
                    # 使用正则提取所有数字（含小数），处理各种格式
                    # 例如 "$15.00 - $18.00", "$25.00", "15.00-18.00" 等
                    numbers = re.findall(r'[\d,]+\.?\d*', price_range)
                    if len(numbers) >= 2:
                        price_range_low = Decimal(numbers[0].replace(',', ''))
                        price_range_high = Decimal(numbers[1].replace(',', ''))
                    elif len(numbers) == 1:
                        price = Decimal(numbers[0].replace(',', ''))
                        price_range_low = price
                        price_range_high = price
                except (Exception, ArithmeticError):
                    logger.debug(f"无法解析价格区间: {price_range}")
                    pass

            # 提取最终价格（已定价的IPO）
            final_price: Decimal | None = None
            price_str = row.get("price")
            if price_str and price_str != "N/A":
                try:
                    final_price = Decimal(price_str.replace("$", "").strip())
                except Exception:
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
            deal_size_mm: Decimal | None = None
            deal_str = row.get("dealSize") or row.get("proposedMarketCap")
            if deal_str and deal_str != "N/A":
                try:
                    # 处理 "$150.0 M" 或 "$150.0" 格式
                    deal_str = deal_str.replace("$", "").replace(",", "").strip()
                    if "M" in deal_str:
                        deal_size_mm = Decimal(deal_str.replace("M", "").strip())
                    elif "B" in deal_str:
                        deal_size_mm = Decimal(deal_str.replace("B", "").strip()) * Decimal("1000")
                    else:
                        deal_size_mm = Decimal(deal_str) / Decimal("1000000")
                except Exception:
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

    def __init__(self, db_manager: Any = None):
        """初始化IPOScoop爬虫."""
        super().__init__(
            name="iposcoop_calendar",
            rate_limit=0.2,  # 每5秒1个请求（保守）
            db_manager=db_manager,
        )

    def fetch(self, **kwargs: Any) -> list[IPOEvent]:
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

    def _parse_calendar(self, soup: Any) -> list[IPOEvent]:
        """解析IPO日历页面."""
        events: list[IPOEvent] = []

        try:
            # 查找IPO表格
            table = soup.find("table", class_="ipolist")
            if not table:
                logger.warning("Could not find IPO calendar table")
                return events

            tbody = table.find("tbody")
            if not tbody:
                logger.warning("Could not find table body")
                return events

            for row in tbody.find_all("tr"):
                try:
                    cells = row.find_all("td")
                    if len(cells) < 8:
                        continue

                    # 提取数据
                    company_name = self._extract_text(cells[0])
                    ticker_link = cells[1].find("a")
                    ticker = (
                        ticker_link.text.strip() if ticker_link else self._extract_text(cells[1])
                    )

                    # 清理ticker（去掉后缀如 .U, .WS 等）
                    ticker = ticker.split(".")[0] if ticker else None

                    lead_managers = self._extract_text(cells[2]) if len(cells) > 2 else None

                    # 解析股数（百万）
                    shares_str = self._extract_text(cells[3]) if len(cells) > 3 else "0"
                    try:
                        shares_offered = (
                            int(float(shares_str.replace(",", "")) * 1000000)
                            if shares_str
                            else None
                        )
                    except ValueError:
                        shares_offered = None

                    # 解析价格区间
                    price_low_str = self._extract_text(cells[4]) if len(cells) > 4 else None
                    price_high_str = self._extract_text(cells[5]) if len(cells) > 5 else None
                    price_range_low: Decimal | None = None
                    price_range_high: Decimal | None = None

                    try:
                        if price_low_str is not None:
                            price_range_low = Decimal(price_low_str)
                    except ValueError:
                        price_range_low = None

                    try:
                        if price_high_str is not None:
                            price_range_high = Decimal(price_high_str)
                    except ValueError:
                        price_range_high = None

                    # 解析交易规模
                    volume_str = self._extract_text(cells[6]) if len(cells) > 6 else None
                    deal_size_mm: Decimal | None = None
                    try:
                        # 格式如 "$ 100.0 mil" 或 "$1.5 bil"
                        volume_clean = (volume_str or "").replace("$", "").replace(",", "").strip()
                        if "mil" in volume_clean.lower():
                            deal_size_mm = Decimal(volume_clean.lower().replace("mil", "").strip())
                        elif "bil" in volume_clean.lower():
                            deal_size_mm = Decimal(
                                volume_clean.lower().replace("bil", "").strip()
                            ) * Decimal("1000")
                        else:
                            deal_size_mm = (
                                Decimal(volume_clean) / Decimal("1000000") if volume_clean else None
                            )
                    except ValueError:
                        deal_size_mm = None

                    # 解析预期交易日期
                    date_str = self._extract_text(cells[7]) if len(cells) > 7 else None
                    expected_date = self._parse_date(date_str)

                    # 获取SCOOP评级（如果可用）
                    scoop_rating = None
                    if len(cells) > 8:
                        rating_text = self._extract_text(cells[8])
                        if rating_text and rating_text != "S/O":
                            scoop_rating = rating_text

                    # 创建IPO事件
                    if ticker and company_name:
                        event = IPOEvent(
                            ticker=ticker,
                            company_name=company_name,
                            expected_date=expected_date,
                            price_range_low=price_range_low,
                            price_range_high=price_range_high,
                            shares_offered=shares_offered,
                            deal_size_mm=deal_size_mm,
                            lead_underwriter=lead_managers,
                            status=(
                                IPOStatus.FILED
                                if expected_date and expected_date >= date.today()
                                else IPOStatus.PRICED
                            ),
                            exchange="NASDAQ",  # 默认假设
                            sector=None,
                        )
                        events.append(event)

                except Exception as e:
                    logger.warning(f"Error parsing IPO row: {e}")
                    continue

            logger.info(f"Parsed {len(events)} IPO events from IPOScoop")

        except Exception as e:
            logger.error(f"Error parsing IPOScoop calendar: {e}")

        return events

    def _extract_text(self, cell: Any) -> Optional[str]:
        """从表格单元格提取文本."""
        if not cell:
            return None
        text = cell.get_text(strip=True)
        return text if text else None

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """解析日期字符串.

        支持格式:
        - "3/27/2026 Friday"
        - "4/6/2026 Week of"
        - "3/27/2026"
        """
        if not date_str:
            return None

        try:
            # 移除多余文字（如 "Friday", "Week of"）
            date_part = date_str.split()[0]

            # 尝试解析 M/D/YYYY 格式
            for fmt in ["%m/%d/%Y", "%m/%d/%y"]:
                try:
                    return datetime.strptime(date_part, fmt).date()
                except ValueError:
                    continue

            logger.warning(f"Could not parse date: {date_str}")
            return None

        except Exception as e:
            logger.debug(f"Date parsing error for '{date_str}': {e}")
            return None


class IPOCalendarAggregator:
    """IPO日历聚合器.

    协调多个数据源，提供统一的IPO日历接口。
    优先使用Nasdaq，失败时回退到IPOScoop。
    """

    def __init__(self, db_manager: Any = None):
        """初始化聚合器."""
        self.nasdaq = NasdaqIPOCalendarCrawler(db_manager)
        self.iposcoop = IPOScoopCrawler(db_manager)
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)

    def fetch_all(self, **kwargs: Any) -> list[IPOEvent]:
        """从所有可用源获取IPO日历.

        优先顺序：Nasdaq -> IPOScoop

        Returns:
            合并后的IPOEvent列表（去重）
        """
        all_events = []

        # 始终同时调用两个数据源，合并后去重，确保不遗漏任何 IPO
        # 尝试Nasdaq（主数据源）
        try:
            nasdaq_events = self.nasdaq.fetch(**kwargs)
            if nasdaq_events:
                all_events.extend(nasdaq_events)
                self.logger.info(f"Got {len(nasdaq_events)} events from Nasdaq")
        except Exception as e:
            self.logger.warning(f"Nasdaq fetch failed: {e}")

        # 始终尝试 IPOScoop（补充数据源），合并结果以避免遗漏
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
        # 获取所有数据，然后过滤即将上市的
        events = self.fetch_all(upcoming=True, priced=True, filed=True)

        # 过滤日期 - 即将上市的是未来日期的
        today = date.today()
        cutoff = today + timedelta(days=days)

        filtered = [e for e in events if e.expected_date and today <= e.expected_date <= cutoff]

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

        filtered = [e for e in events if e.expected_date and cutoff <= e.expected_date <= today]

        # 按日期倒序
        filtered.sort(key=lambda x: x.expected_date or date.min, reverse=True)

        return filtered
