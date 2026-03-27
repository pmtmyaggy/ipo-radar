"""机构持仓爬虫 - 从SEC EDGAR爬取13F报告.

PRD 3.6模块：机构持仓爬虫
- 每季度13F报告提交后爬取
- 提取机构名称、持股数量、持股市值、环比变化
- 计算新增机构数量、机构总持仓变化、前十大持仓机构名单
"""

import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import requests
from bs4 import BeautifulSoup

from .base import BaseCrawler
from .models.schemas import InstitutionalHolding

logger = logging.getLogger(__name__)


class HoldingsFetcher(BaseCrawler):
    """13F机构持仓爬虫.

    从SEC EDGAR获取机构持仓数据，跟踪季度变化。
    """

    # SEC EDGAR 13F搜索URL
    EDGAR_13F_URL = "https://www.sec.gov/cgi-bin/browse-edgar"

    # 13F信息表URL模板
    HOLDINGS_URL_TEMPLATE = (
        "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_number}/infotable.xml"
    )

    def __init__(self, db_manager: Any = None) -> None:
        """初始化持仓爬虫."""
        super().__init__(
            name="holdings_fetcher",
            rate_limit=0.2,  # SEC要求5秒间隔
            db_manager=db_manager,
        )
        self.logger = logging.getLogger(__name__)

        # 初始化requests session
        self.session = requests.Session()
        # 设置User-Agent
        from src.crawler.utils.user_agent import UserAgentManager

        ua = UserAgentManager()
        self.session.headers.update(ua.get_headers(user_agent_type="edgar"))
        
        # CUSIP 到 Ticker 的内存级缓存
        self._cusip_cache: dict[str, str] = {}

    def fetch(self, **kwargs: Any) -> list[InstitutionalHolding]:
        """获取机构持仓数据.

        Args:
            ticker: 股票代码（可选）
            cik: 机构CIK（可选）
            quarter: 季度，格式 '2024-Q1'（可选，默认最近季度）

        Returns:
            List[InstitutionalHolding] 持仓列表
        """
        ticker = kwargs.get("ticker")
        cik = kwargs.get("cik")
        quarter = kwargs.get("quarter")

        if ticker:
            return self._fetch_by_ticker(ticker, quarter)
        elif cik:
            return self._fetch_by_institution(cik, quarter)
        else:
            return self._fetch_recent_filings(quarter)

    def _fetch_by_ticker(
        self, ticker: str, quarter: str | None = None
    ) -> list[InstitutionalHolding]:
        """通过股票代码获取持仓数据.

        搜索所有包含该股票的13F报告。
        """
        holdings: list[InstitutionalHolding] = []

        try:
            # 获取最近提交的13F报告列表
            filings = self._search_13f_filings(quarter)

            for filing in filings:
                try:
                    # 获取该机构的持仓详情
                    institution_holdings = self._parse_holdings_xml(
                        filing["cik"],
                        filing["accession_number"],
                        filing["filing_date"],
                        filing.get("institution_name", ""),
                    )

                    # 筛选指定股票
                    for h in institution_holdings:
                        if h.ticker == ticker.upper():
                            holdings.append(h)

                except Exception as e:
                    self.logger.warning(f"Failed to parse holdings for CIK {filing['cik']}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error fetching holdings for {ticker}: {e}")

        return holdings

    def _fetch_by_institution(
        self, cik: str, quarter: str | None = None
    ) -> list[InstitutionalHolding]:
        """通过机构CIK获取其所有持仓."""
        holdings: list[InstitutionalHolding] = []

        try:
            # 获取该机构的最新13F报告
            params = {
                "action": "getcompany",
                "CIK": cik,
                "type": "13F-HR",
                "count": "1",
                "output": "atom",
            }

            response = self.session.get(self.EDGAR_13F_URL, params=params, timeout=30)
            response.raise_for_status()

            # 解析获取accession number
            entries = self._parse_edgar_atom(response.text)

            if entries:
                entry = entries[0]
                holdings = self._parse_holdings_xml(
                    cik,
                    entry["accession_number"],
                    entry["filing_date"],
                    entry.get("institution_name", ""),
                )

        except Exception as e:
            self.logger.error(f"Error fetching holdings for CIK {cik}: {e}")

        return holdings

    def _fetch_recent_filings(self, quarter: str | None = None) -> list[InstitutionalHolding]:
        """获取最近提交的13F报告."""
        holdings: list[InstitutionalHolding] = []

        try:
            filings = self._search_13f_filings(quarter, count=50)

            for filing in filings:
                try:
                    institution_holdings = self._parse_holdings_xml(
                        filing["cik"],
                        filing["accession_number"],
                        filing["filing_date"],
                        filing.get("institution_name", ""),
                    )
                    holdings.extend(institution_holdings)

                except Exception as e:
                    self.logger.warning(f"Failed to parse filing {filing['accession_number']}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error fetching recent filings: {e}")

        return holdings

    def _search_13f_filings(
        self, quarter: str | None = None, count: int = 100
    ) -> list[dict[str, str]]:
        """搜索13F报告.

        Returns:
            List of dicts with keys: cik, accession_number, filing_date, institution_name
        """
        filings: list[dict[str, str]] = []

        params = {
            "action": "getcurrent",
            "type": "13F-HR",
            "output": "atom",
        }

        try:
            response = self.session.get(self.EDGAR_13F_URL, params=params, timeout=30)
            response.raise_for_status()

            entries = self._parse_edgar_atom(response.text)

            # 筛选指定季度
            if quarter:
                entries = [e for e in entries if quarter in e.get("filing_date", "")]

            filings = entries[:count]

        except Exception as e:
            self.logger.error(f"Error searching 13F filings: {e}")

        return filings

    def _parse_edgar_atom(self, xml_content: str) -> list[dict[str, str]]:
        """解析EDGAR ATOM feed."""
        entries: list[dict[str, str]] = []

        try:
            soup = BeautifulSoup(xml_content, "xml")

            for entry in soup.find_all("entry"):
                try:
                    entry_data = {
                        "title": entry.find("title").text if entry.find("title") else "",
                        "cik": "",
                        "accession_number": "",
                        "filing_date": (
                            entry.find("updated").text[:10] if entry.find("updated") else ""
                        ),
                        "institution_name": "",
                    }

                    # 提取CIK和accession number
                    link = entry.find("link", href=True)
                    if link:
                        href = link["href"]
                        # 从URL提取CIK和accession number
                        parts = href.split("/")
                        if len(parts) >= 3:
                            entry_data["cik"] = parts[-2]
                            entry_data["accession_number"] = parts[-1].replace("-", "")

                    # 提取机构名称
                    summary = entry.find("summary")
                    if summary:
                        entry_data["institution_name"] = summary.text.strip()[:100]

                    entries.append(entry_data)

                except Exception as e:
                    self.logger.warning(f"Error parsing entry: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error parsing ATOM feed: {e}")

        return entries

    def _parse_holdings_xml(
        self,
        cik: str,
        accession_number: str,
        filing_date: str,
        institution_name: str,
    ) -> list[InstitutionalHolding]:
        """解析13F持仓XML文件.

        13F报告通常以XML格式提供持仓详情。
        """
        holdings: list[InstitutionalHolding] = []

        try:
            # 构建持仓XML URL
            url = self.HOLDINGS_URL_TEMPLATE.format(cik=cik, accession_number=accession_number)

            response = self.session.get(url, timeout=30)

            if response.status_code == 404:
                # 尝试备用格式
                url = url.replace("infotable.xml", "form13fInfoTable.xml")
                response = self.session.get(url, timeout=30)

            response.raise_for_status()

            # 解析XML
            soup = BeautifulSoup(response.content, "xml")

            # 查找所有持仓条目
            info_tables = soup.find_all("infoTable") or soup.find_all("ns1:infoTable")

            for table in info_tables:
                try:
                    holding = self._extract_holding_from_table(
                        table, cik, filing_date, institution_name
                    )
                    if holding:
                        holdings.append(holding)

                except Exception as e:
                    self.logger.warning(f"Error extracting holding: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error parsing holdings XML for {cik}: {e}")

        return holdings

    def _extract_holding_from_table(
        self,
        table: Any,
        cik: str,
        filing_date: str,
        institution_name: str,
    ) -> InstitutionalHolding | None:
        """从infoTable提取单个持仓."""
        try:
            # 提取字段（处理命名空间）
            name_of_issuer = self._get_xml_text(table, ["nameOfIssuer", "ns1:nameOfIssuer"])
            cusip = self._get_xml_text(table, ["cusip", "ns1:cusip"])

            #  shares
            shares_str = self._get_xml_text(table, ["sshPrnamt", "ns1:sshPrnamt"])
            shares = int(shares_str) if shares_str else 0

            # 市值（通常是千美元）
            value_str = self._get_xml_text(table, ["value", "ns1:value"])
            value = Decimal(value_str) * 1000 if value_str else Decimal("0")

            # 尝试获取ticker（从CUSIP映射，简化处理）
            issuer_name = name_of_issuer or "UNKNOWN"
            ticker = self._cusip_to_ticker(cusip) or issuer_name[:5].upper()
            report_date = self._parse_filing_date(filing_date)

            return InstitutionalHolding(
                cik=cik,
                institution_name=institution_name or "Unknown Institution",
                ticker=ticker,
                report_date=report_date,
                shares_held=shares,
                value=value,
            )

        except Exception as e:
            self.logger.warning(f"Error extracting holding: {e}")
            return None

    def _get_xml_text(self, element: Any, tag_names: list[str]) -> str | None:
        """从XML元素获取文本（尝试多个标签名）."""
        for tag in tag_names:
            child = element.find(tag)
            if child and child.text:
                return str(child.text).strip()
        return None

    def _cusip_to_ticker(self, cusip: str | None) -> str | None:
        """CUSIP转股票代码 (通过 SEC EDGAR getcompany 接口查询).

        获取并缓存查询结果以减小请求量。
        """
        if not cusip:
            return None
        
        cusip = cusip.strip()
        if cusip in self._cusip_cache:
            return self._cusip_cache[cusip]
            
        try:
            params = {
                "action": "getcompany",
                "CIK": cusip,
                "output": "atom",
            }
            # 如果请求过于频繁，可加入轻度的 self.rate_limiter 休眠
            response = self.session.get(self.EDGAR_13F_URL, params=params, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "xml")
                # SEC ATOM XML 中包含类似 <ticker>TSLA</ticker> 或者能从 title/summary 获取
                # 有些返回里面没有明确的 ticker 标签，可以尝试提取公司名称
                companies = soup.find_all("company-info")
                if not companies:
                    companies = soup.find_all("company")
                    
                # 最简单是从 ATOM 的 entries 中提取，但 SEC EDGAR 返回的往往不直接给 ticker
                # 所以我们简单在网页正则匹配: TICKER: 
                match = re.search(r"&amp;CIK=([a-zA-Z0-9]+)", response.text)
                if match:
                    # 获取了 CIK 后可能需要别的方法取 ticker，但是通常 getcompany XML 中有一段
                    pass
                    
                # 另一个从 SEC 获取 ticker 的常见做法是从 company-info 中找
                # 兼容：如果获取不到，直接解析 feed title (例如: CIK 0001018724 / AMAZON COM INC (AMZN) )
                title_elem = soup.find("title")
                title_text = title_elem.text if title_elem else ""
                
                ticker_match = re.search(r'\(([A-Z]+)\)', title_text)
                if ticker_match:
                    ticker = ticker_match.group(1)
                    self._cusip_cache[cusip] = ticker
                    return ticker
                    
            self._cusip_cache[cusip] = None
            return None
            
        except Exception as e:
            self.logger.debug(f"Failed to resolve CUSIP {cusip} to ticker: {e}")
            return None

    def _parse_filing_date(self, date_str: str) -> date:
        """解析日期字符串."""
        try:
            return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        except Exception:
            return date.today()


class InstitutionalHoldingsAnalyzer:
    """机构持仓分析器.

    计算机构持仓变化指标。
    """

    def __init__(self, db_manager: Any = None) -> None:
        """初始化分析器."""
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)

    def analyze_holdings_change(
        self, ticker: str, current_quarter: str, previous_quarter: str
    ) -> dict[str, Any]:
        """分析持仓季度变化.

        Returns:
            Dict with keys:
                - new_institutions: 新增机构数量
                - dropped_institutions: 退出机构数量
                - total_institutions: 总机构数
                - total_shares_change: 总持股数变化
                - total_value_change_pct: 总市值变化%
                - top_10_holders: 前十大持仓机构
        """
        result = {
            "new_institutions": 0,
            "dropped_institutions": 0,
            "total_institutions": 0,
            "total_shares_change": 0,
            "total_value_change_pct": 0.0,
            "top_10_holders": [],
        }

        try:
            # 获取当前季度和上一季度持仓
            current = self._get_holdings_for_quarter(ticker, current_quarter)
            previous = self._get_holdings_for_quarter(ticker, previous_quarter)

            # 计算新增和退出机构
            current_ciks = {h.cik for h in current}
            previous_ciks = {h.cik for h in previous}

            result["new_institutions"] = len(current_ciks - previous_ciks)
            result["dropped_institutions"] = len(previous_ciks - current_ciks)
            result["total_institutions"] = len(current_ciks)

            # 计算总持股变化
            current_shares = sum(h.shares_held for h in current)
            previous_shares = sum(h.shares_held for h in previous)
            result["total_shares_change"] = current_shares - previous_shares

            # 计算市值变化
            current_value = sum((h.value or Decimal("0")) for h in current)
            previous_value = sum((h.value or Decimal("0")) for h in previous)
            if previous_value > 0:
                result["total_value_change_pct"] = float(
                    (current_value - previous_value) / previous_value * 100
                )

            # 前十大持仓机构
            sorted_holdings = sorted(current, key=lambda x: x.value or Decimal("0"), reverse=True)
            result["top_10_holders"] = [
                {
                    "cik": h.cik,
                    "name": h.institution_name,
                    "shares": h.shares_held,
                    "value": float(h.value or Decimal("0")),
                }
                for h in sorted_holdings[:10]
            ]

        except Exception as e:
            self.logger.error(f"Error analyzing holdings change for {ticker}: {e}")

        return result

    def _get_holdings_for_quarter(self, ticker: str, quarter: str) -> list[InstitutionalHolding]:
        """从数据库获取指定季度持仓."""
        holdings: list[InstitutionalHolding] = []

        if not self.db_manager:
            return holdings

        try:
            from .models.database import InstitutionalHoldingModel

            with self.db_manager.session_scope() as session:
                records = session.query(InstitutionalHoldingModel).filter_by(ticker=ticker).all()

                for r in records:
                    if quarter in r.report_date.isoformat():
                        holdings.append(
                            InstitutionalHolding(
                                cik=r.cik,
                                institution_name=r.institution_name,
                                ticker=r.ticker,
                                report_date=r.report_date,
                                shares_held=r.shares_held,
                                value=r.value,
                            )
                        )

        except Exception as e:
            self.logger.error(f"Error fetching holdings from DB: {e}")

        return holdings


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    fetcher = HoldingsFetcher()

    # 测试获取最近提交的13F
    print("Testing 13F holdings fetcher...")
    print("Fetcher initialized successfully")
