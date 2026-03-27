"""S-1招股说明书解析器.

从SEC EDGAR下载S-1文件并解析关键信息：
- 财务指标（营收、毛利率、现金等）
- 禁售期条款
- 承销商信息
- 募集资金用途
"""

import logging
import os
import re
from datetime import date, datetime
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseCrawler
from .models.schemas import S1Filing, LockupInfo

logger = logging.getLogger(__name__)


class S1Parser(BaseCrawler):
    """S-1文件解析器.

    负责：
    1. 下载S-1 HTML文件
    2. 提取关键财务指标
    3. 解析禁售期条款
    4. 提取承销商信息
    """

    # 禁售期相关关键词模式
    LOCKUP_PATTERNS = [
        r"(\d+)\s*days?.*lock[\s-]?up",
        r"lock[\s-]?up.*?(\d+)\s*days?",
        r"(\d+)\s*months?.*lock[\s-]?up",
        r"for\s+a\s+period\s+of\s+(\d+).*days?",
        r"(\d+)-day\s+lock[\s-]?up",
        r"(\d+)-month\s+lock[\s-]?up",
    ]

    # 持有人类型关键词
    HOLDER_KEYWORDS = {
        "founders": ["founder", "chief executive", "ceo", "executive officer", "director"],
        "vc": ["venture capital", "vc fund", "series a", "series b", "series c"],
        "pe": ["private equity", "sponsor", "investment fund", "equity firm"],
        "employees": ["employee", "option holder", "restricted stock", "stock option"],
    }

    def __init__(self, db_manager: Any = None):
        """初始化S-1解析器."""
        super().__init__(
            name="s1_parser",
            rate_limit=5.0,
            db_manager=db_manager,
        )
        # LLM 可用性标记：仅在配置了 API Key 时启用
        self._llm_enabled = bool(os.getenv("OPENAI_API_KEY") or os.getenv("LITELLM_API_KEY"))

    def _llm_summarize(self, text: str, prompt: str, max_chars: int = 4000) -> Optional[str]:
        """使用 LLM 生成结构化摘要。

        如果 LLM 不可用或调用失败，返回 None（由调用方降级到正则截取）。

        Args:
            text: 待摘要的原始文本
            prompt: 系统提示词
            max_chars: 发送给 LLM 的最大字符数

        Returns:
            LLM 生成的摘要文本，或 None
        """
        if not self._llm_enabled:
            return None

        try:
            import litellm

            # 截取文本避免超出 token 限制
            truncated_text = text[:max_chars]

            response = litellm.completion(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": truncated_text},
                ],
                max_tokens=500,
                temperature=0.1,
            )

            content = response.choices[0].message.content
            return content.strip() if content else None

        except Exception as e:
            logger.warning(f"LLM 摘要调用失败，将降级为正则截取: {e}")
            return None

    def fetch(self, **kwargs: Any) -> Optional[S1Filing]:
        """下载并解析S-1文件.

        Args:
            **kwargs:
                - url: S-1文件URL
                - cik: 公司CIK
                - filed_date: 提交日期

        Returns:
            S1Filing对象或None
        """
        url = kwargs.get("url")
        cik = kwargs.get("cik")
        filed_date = kwargs.get("filed_date")

        if not url:
            logger.error("S-1 URL is required")
            return None

        try:
            # 下载S-1文件
            html_content = self._download_s1(url)
            if not html_content:
                return None

            # 解析文件
            filing = self._parse_s1(html_content, cik, filed_date, url)

            return filing

        except Exception as e:
            logger.error(f"Failed to fetch/parse S-1 from {url}: {e}")
            return None

    def _download_s1(self, url: str) -> Optional[str]:
        """下载S-1 HTML文件.

        Args:
            url: S-1文件URL

        Returns:
            HTML内容或None
        """
        try:
            response = self._request(
                url,
                user_agent_type="edgar",
            )
            response.raise_for_status()

            return str(response.text)

        except requests.RequestException as e:
            logger.error(f"Failed to download S-1 from {url}: {e}")
            return None

    def _parse_s1(
        self,
        html: str,
        cik: Optional[str],
        filed_date: Optional[date],
        url: str,
    ) -> S1Filing:
        """解析S-1 HTML内容.

        Args:
            html: HTML内容
            cik: 公司CIK
            filed_date: 提交日期
            url: 文件URL

        Returns:
            S1Filing对象
        """
        soup = self._parse_html(html)

        # 提取各章节文本
        text = soup.get_text(separator="\n")

        filing = S1Filing(
            cik=cik or "",
            filed_date=filed_date or date.today(),
            s1_url=url,
        )

        # 解析财务指标
        self._parse_financials(soup, text, filing)

        # 解析禁售期信息
        self._parse_lockup(text, filing)

        # 解析募集资金用途
        self._parse_use_of_proceeds(soup, text, filing)

        # 解析风险因素
        self._parse_risk_factors(soup, text, filing)

        return filing

    def _parse_financials(self, soup: BeautifulSoup, text: str, filing: S1Filing) -> None:
        """解析财务指标.

        从Financial Statements章节提取：
        - 营收
        - 毛利率
        - 净利润
        - 现金及等价物
        - 总债务
        """
        try:
            # 查找财务数据表格
            tables = soup.find_all("table")

            for table in tables:
                # 尝试识别财务数据表
                header = table.get_text().lower()

                if "revenue" in header or "total revenue" in header:
                    filing.revenue_3yr = self._extract_revenue_data(table)

                if "balance sheet" in header or "assets" in header:
                    filing.cash_and_equivalents = self._extract_cash(table)
                    filing.total_debt = self._extract_debt(table)

            # 从文本中提取毛利率
            filing.gross_margin = self._extract_gross_margin(text)

        except Exception as e:
            logger.warning(f"Error parsing financials: {e}")

    def _extract_revenue_data(self, table: Any) -> list[tuple[int, Decimal]]:
        """提取营收数据。

        动态从表头解析年份列，不再硬编码假设当前年份。
        """
        revenues = []
        try:
            rows = table.find_all("tr")

            # 先从表头行提取年份信息
            header_years: list[int | None] = []
            for row in rows:
                ths = row.find_all(["th", "td"])
                if len(ths) >= 2:
                    year_candidates = []
                    for th in ths[1:]:
                        text = th.get_text().strip()
                        year_match = re.search(r'(20\d{2})', text)
                        if year_match:
                            year_candidates.append(int(year_match.group(1)))
                        else:
                            year_candidates.append(None)
                    if any(y is not None for y in year_candidates):
                        header_years = year_candidates
                        break

            # 在数据行中查找营收
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    label = cells[0].get_text().strip().lower()
                    if "revenue" in label or "net revenue" in label or "total revenue" in label or "sales" in label:
                        for i, cell in enumerate(cells[1:]):
                            value = self._parse_money(cell.get_text())
                            if value:
                                # 使用从表头解析的年份，如果没有则按倒序推断
                                if i < len(header_years) and header_years[i] is not None:
                                    year = header_years[i]
                                else:
                                    # 降级：从当前日期倒推
                                    from datetime import date as _date
                                    year = _date.today().year - (len(cells) - 2 - i)
                                revenues.append((year, value))
                        break
        except Exception as e:
            logger.debug(f"提取营收数据异常: {e}")

        return revenues

    def _extract_cash(self, table: Any) -> Optional[Decimal]:
        """提取现金及等价物."""
        try:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    label = cells[0].get_text().strip().lower()
                    if "cash and cash equivalents" in label or "cash and equivalents" in label:
                        return self._parse_money(cells[1].get_text())
        except Exception:
            pass
        return None

    def _extract_debt(self, table: Any) -> Optional[Decimal]:
        """提取总债务."""
        try:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    label = cells[0].get_text().strip().lower()
                    if "total debt" in label or "long-term debt" in label:
                        return self._parse_money(cells[1].get_text())
        except Exception:
            pass
        return None

    def _extract_gross_margin(self, text: str) -> Optional[Decimal]:
        """从文本中提取毛利率."""
        # 查找毛利率相关的句子
        patterns = [
            r"gross margin.*?([\d.]+)%",
            r"gross profit margin.*?([\d.]+)%",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return Decimal(match.group(1)) / 100
                except InvalidOperation:
                    pass

        return None

    def _parse_lockup(self, text: str, filing: S1Filing) -> None:
        """解析禁售期条款.

        从"Shares Eligible for Future Sale"章节提取。
        """
        try:
            # 搜索禁售期天数
            lockup_days = None

            for pattern in self.LOCKUP_PATTERNS:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        lockup_days = int(match.group(1))
                        break
                    except (ValueError, IndexError):
                        continue

            if lockup_days:
                filing.lockup_days = lockup_days

                # 计算到期日（假设IPO日期在提交后3-6个月）
                # 这里简化处理，使用提交日期+6个月作为预估
                estimated_ipo = filing.filed_date + timedelta(days=180)
                filing.lockup_expiry_date = estimated_ipo + timedelta(days=lockup_days)

            # 识别持有人类型
            filing.locked_holders = self._identify_holder_types(text)

            # 检查是否有提前解锁条款
            early_release_keywords = ["early release", "early termination", "waiver", "waive"]
            filing.early_release_provisions = any(
                kw in text.lower() for kw in early_release_keywords
            )

        except Exception as e:
            logger.warning(f"Error parsing lockup: {e}")

    def _identify_holder_types(self, text: str) -> list[str]:
        """识别持有人类型."""
        holders = []
        text_lower = text.lower()

        for holder_type, keywords in self.HOLDER_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                holders.append(holder_type)

        return holders if holders else ["unknown"]

    def _parse_use_of_proceeds(self, soup: BeautifulSoup, text: str, filing: S1Filing) -> None:
        """解析募集资金用途。

        优先使用 LLM 生成结构化摘要，降级为截取前500字符。
        """
        try:
            section = self._find_section(soup, text, "use of proceeds")
            if not section:
                return

            # 尝试 LLM 摘要
            llm_result = self._llm_summarize(
                section,
                "你是一位 SEC 招股说明书分析专家。请从以下 'Use of Proceeds' 章节中提取资金用途的结构化摘要，"
                "包括具体用途项和预计比例（如果有）。用简洁的中文列表输出，每项不超过一行。",
            )

            if llm_result:
                filing.use_of_proceeds = llm_result
            else:
                # 降级：截取前500字符
                filing.use_of_proceeds = section[:500].strip()

        except Exception as e:
            logger.warning(f"Error parsing use of proceeds: {e}")

    def _parse_risk_factors(self, soup: BeautifulSoup, text: str, filing: S1Filing) -> None:
        """解析风险因素。

        优先使用 LLM 提取前5条关键风险要点，降级为截取前1000字符。
        """
        try:
            section = self._find_section(soup, text, "risk factors")
            if not section:
                return

            # 尝试 LLM 摘要
            llm_result = self._llm_summarize(
                section,
                "你是一位 SEC 招股说明书分析专家。请从以下 'Risk Factors' 章节中提取最关键的5条风险要点。"
                "用简洁的中文列表输出，每条风险一行，格式为 '1. 风险描述'。聚焦对投资者决策影响最大的风险。",
            )

            if llm_result:
                filing.risk_factors_summary = llm_result
            else:
                # 降级：截取前1000字符
                filing.risk_factors_summary = section[:1000].strip()

        except Exception as e:
            logger.warning(f"Error parsing risk factors: {e}")

    def _find_section(self, soup: BeautifulSoup, text: str, section_name: str) -> Optional[str]:
        """查找特定章节的内容."""
        try:
            # 尝试通过标题查找
            headers = soup.find_all(["h1", "h2", "h3", "h4", "h5"])
            for header in headers:
                if section_name.lower() in header.get_text().lower():
                    # 获取后续段落直到下一个标题
                    content = []
                    next_elem = header.find_next_sibling()
                    while next_elem and next_elem.name not in ["h1", "h2", "h3", "h4", "h5"]:
                        if next_elem.name in ["p", "div"]:
                            content.append(next_elem.get_text())
                        next_elem = next_elem.find_next_sibling()

                    return "\n".join(content)

            # 备用：从文本中查找
            pattern = rf"{section_name}.*?(?=\n\s*\n|\Z)"
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(0)

        except Exception:
            pass

        return None

    def _clean_html(self, html: str) -> str:
        """清理HTML标签.

        Args:
            html: HTML字符串

        Returns:
            清理后的文本
        """
        soup = BeautifulSoup(html, "lxml")
        return str(soup.get_text(separator=" "))

    def _parse_money(self, text: str) -> Optional[Decimal]:
        """解析货币金额.

        处理格式如：$1,234,567 / 1.2 million / 1.2M
        """
        if not text:
            return None

        try:
            text = text.strip().replace(",", "").replace("$", "")

            # 处理括号表示的负数
            if text.startswith("(") and text.endswith(")"):
                text = "-" + text[1:-1]

            # 提取数字（支持负数）
            match = re.search(r"-?[\d.]+", text)
            if not match:
                return None

            value = Decimal(match.group())

            # 处理单位
            text_lower = text.lower()
            if "million" in text_lower or "m" in text_lower:
                value *= 1_000_000
            elif "billion" in text_lower or "b" in text_lower:
                value *= 1_000_000_000
            elif "thousand" in text_lower or "k" in text_lower:
                value *= 1_000

            return value

        except (InvalidOperation, ValueError):
            return None

    def parse_lockup_info(self, s1_filing: S1Filing, ipo_date: date) -> Optional[LockupInfo]:
        """从S-1解析结果生成LockupInfo.

        Args:
            s1_filing: S-1解析结果
            ipo_date: IPO日期

        Returns:
            LockupInfo对象或None
        """
        if not s1_filing.lockup_days:
            return None

        try:
            lockup = LockupInfo(
                ticker="",  # 需要在调用时填充
                ipo_date=ipo_date,
                lockup_days=s1_filing.lockup_days,
                lockup_expiry_date=ipo_date + timedelta(days=s1_filing.lockup_days),
                shares_locked=s1_filing.shares_locked,
                locked_holders=s1_filing.locked_holders,
                early_release_provisions=s1_filing.early_release_provisions or False,
                total_shares_outstanding=s1_filing.total_shares_outstanding,
                float_after_ipo=s1_filing.float_after_ipo,
                parsed_from_s1=True,
            )

            # 计算供应冲击
            if lockup.shares_locked and lockup.float_after_ipo:
                lockup.supply_impact_pct = Decimal(lockup.shares_locked) / Decimal(
                    lockup.float_after_ipo
                )

            return lockup

        except Exception as e:
            logger.error(f"Failed to create LockupInfo: {e}")
            return None
