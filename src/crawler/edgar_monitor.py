"""SEC EDGAR 实时监控器.

监控 SEC EDGAR 系统的新文件提交，包括：
- S-1 文件（IPO申请）
- 424B4 文件（最终招股书）
- 13F 文件（机构持仓）

使用 EFTS (EDGAR Full Text Search) API。
"""

import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional
from urllib.parse import urlencode

import requests

from .base import BaseCrawler
from .models.schemas import IPOEvent, IPOStatus

logger = logging.getLogger(__name__)


class EdgarObserver(ABC):
    """EDGAR观察者接口.
    
    实现此接口以接收新文件通知。
    """
    
    @abstractmethod
    def on_new_s1(self, filing: dict) -> None:
        """当新的S-1文件提交时调用.
        
        Args:
            filing: 文件信息字典
        """
        pass
    
    @abstractmethod
    def on_new_424b4(self, filing: dict) -> None:
        """当新的424B4文件提交时调用."""
        pass


class EdgarMonitor(BaseCrawler):
    """SEC EDGAR 实时监控器.
    
    轮询 EDGAR EFTS API 检测新文件。
    
    EFTS API: https://efts.sec.gov/LATEST/search-index
    
    Attributes:
        poll_interval: 轮询间隔（秒），默认60
        observers: 观察者列表
        last_check: 上次检查时间
    """
    
    EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
    EDGAR_BASE = "https://www.sec.gov/Archives/edgar/data"
    
    # 需要监控的表单类型
    MONITORED_FORMS = ["S-1", "S-1/A", "424B4", "13F-HR"]
    
    def __init__(
        self,
        db_manager: Any = None,
        poll_interval: int = 60,
    ) -> None:
        """初始化EDGAR监控器.
        
        Args:
            db_manager: 数据库管理器
            poll_interval: 轮询间隔（秒），默认60
        """
        super().__init__(
            name="edgar_monitor",
            rate_limit=5.0,  # SEC限制10次/秒，我们使用5次/秒
            db_manager=db_manager,
        )
        
        self.poll_interval = poll_interval
        self._observers: list[EdgarObserver] = []
        self._last_check: Optional[datetime] = None
        self._running = False
        self._running_lock = threading.Lock()
    
    def register_observer(self, observer: EdgarObserver) -> None:
        """注册观察者.
        
        Args:
            observer: 观察者实例
        """
        self._observers.append(observer)
        logger.info(f"Registered observer: {observer.__class__.__name__}")
    
    def unregister_observer(self, observer: EdgarObserver) -> None:
        """注销观察者."""
        if observer in self._observers:
            self._observers.remove(observer)
    
    def _notify_s1(self, filing: dict) -> None:
        """通知所有观察者新的S-1文件."""
        for observer in self._observers:
            try:
                observer.on_new_s1(filing)
            except Exception as e:
                logger.error(f"Observer {observer} failed to handle S-1: {e}")
    
    def _notify_424b4(self, filing: dict[str, Any]) -> None:
        """通知所有观察者新的424B4文件."""
        for observer in self._observers:
            try:
                observer.on_new_424b4(filing)
            except Exception as e:
                logger.error(f"Observer {observer} failed to handle 424B4: {e}")
    
    def fetch(self, **kwargs: Any) -> list[dict[str, Any]]:
        """获取新提交的文件.
        
        Args:
            **kwargs:
                - start_date: 开始日期
                - end_date: 结束日期
                - form_types: 表单类型列表
        
        Returns:
            文件信息列表
        """
        start_date = kwargs.get("start_date", date.today() - timedelta(days=1))
        end_date = kwargs.get("end_date", date.today())
        form_types = kwargs.get("form_types", self.MONITORED_FORMS)
        
        all_filings: list[dict[str, Any]] = []
        
        for form_type in form_types:
            filings = self._search_filings(form_type, start_date, end_date)
            all_filings.extend(filings)
        
        return all_filings
    
    def _search_filings(
        self,
        form_type: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """搜索特定类型的文件.
        
        Args:
            form_type: 表单类型，如"S-1"
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            文件列表
        """
        params = {
            "q": f'formType:"{form_type}"',
            "dateRange": "custom",
            "startdt": start_date.strftime("%Y-%m-%d"),
            "enddt": end_date.strftime("%Y-%m-%d"),
            "page": 1,
            "pageSize": 100,
        }
        
        url = f"{self.EFTS_URL}?{urlencode(params)}"
        
        try:
            response = self._request(
                url,
                user_agent_type="edgar",  # 使用EDGAR专用User-Agent
            )
            response.raise_for_status()
            
            data = response.json()
            return self._parse_search_results(data, form_type)
            
        except Exception as e:
            logger.error(f"Failed to search {form_type} filings: {e}")
            return []
    
    def _parse_search_results(self, data: dict[str, Any], form_type: str) -> list[dict[str, Any]]:
        """解析搜索响应.
        
        Args:
            data: API响应数据
            form_type: 查询的表单类型
        
        Returns:
            文件信息列表
        """
        filings: list[dict[str, Any]] = []
        
        try:
            hits = data.get("hits", {}).get("hits", [])
            
            for hit in hits:
                source = hit.get("_source", {})
                
                filing = {
                    "cik": source.get("ciks", [None])[0],
                    "company_name": source.get("display_names", [None])[0],
                    "form_type": source.get("form") or form_type,
                    "filed_date": source.get("file_date"),
                    "filing_url": self._build_filing_url(source),
                    "description": source.get("description", ""),
                }
                
                filings.append(filing)
            
            return filings
            
        except Exception as e:
            logger.error(f"Error parsing search results: {e}")
            return []
    
    def _build_filing_url(self, source: dict[str, Any]) -> str:
        """构建文件URL.
        
        Args:
            source: 文件源数据
        
        Returns:
            完整的EDGAR文件URL
        """
        ciks = source.get("ciks", [])
        cik = ciks[0] if ciks else None
        accession = source.get("adsh", "").replace("-", "")
        
        if not cik or not accession:
            return ""
        
        # 格式化CIK（补零到10位）
        cik_padded = str(cik).zfill(10)
        
        # 构建URL
        url = f"{self.EDGAR_BASE}/{cik_padded}/{accession}"
        
        return url
    
    def poll(
        self,
        callback: Callable[[list[dict[str, Any]]], None] | None = None,
    ) -> list[dict[str, Any]]:
        """执行一次轮询.
        
        检查自上次轮询以来的新文件。
        
        Args:
            callback: 可选的回调函数
        
        Returns:
            新文件列表
        """
        now = datetime.now()
        
        # 确定查询时间范围
        if self._last_check:
            start_date = self._last_check.date()
        else:
            start_date = date.today() - timedelta(days=1)
        
        end_date = now.date()
        
        # 获取新文件
        new_filings = self.fetch(
            start_date=start_date,
            end_date=end_date,
        )
        
        # 分类并通知
        s1_filings = [f for f in new_filings if "S-1" in f.get("form_type", "")]
        b4_filings = [f for f in new_filings if "424B4" in f.get("form_type", "")]
        
        for filing in s1_filings:
            self._notify_s1(filing)
        
        for filing in b4_filings:
            self._notify_424b4(filing)
        
        # 更新上次检查时间
        self._last_check = now
        
        # 调用回调
        if callback:
            callback(new_filings)
        
        logger.info(f"Poll completed: {len(new_filings)} new filings ({len(s1_filings)} S-1, {len(b4_filings)} 424B4)")
        
        return new_filings
    
    def start_monitoring(
        self,
        callback: Callable[[list[dict[str, Any]]], None] | None = None,
    ) -> None:
        """开始持续监控.
        
        警告：此方法会阻塞当前线程！
        建议在后台线程中运行。
        
        Args:
            callback: 每次轮询后的回调函数
        """
        with self._running_lock:
            self._running = True
        logger.info(f"Starting EDGAR monitoring (interval: {self.poll_interval}s)")
        
        while True:
            with self._running_lock:
                if not self._running:
                    break
            try:
                self.poll(callback)
            except Exception as e:
                logger.error(f"Error during polling: {e}")
            
            # 等待下次轮询
            time.sleep(self.poll_interval)
    
    def stop_monitoring(self) -> None:
        """停止监控."""
        with self._running_lock:
            self._running = False
        logger.info("Stopping EDGAR monitoring")
    
    def get_s1_filings(
        self,
        days: int = 7,
    ) -> list[dict]:
        """获取最近的S-1文件.
        
        Args:
            days: 过去多少天
        
        Returns:
            S-1文件列表
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        return self._search_filings("S-1", start_date, end_date)
    
    def get_424b4_filings(
        self,
        days: int = 7,
    ) -> list[dict]:
        """获取最近的424B4文件.
        
        Args:
            days: 过去多少天
        
        Returns:
            424B4文件列表
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        return self._search_filings("424B4", start_date, end_date)


class S1FilingHandler(EdgarObserver):
    """S-1文件处理器示例.
    
    当新的S-1文件提交时，自动下载并解析。
    """
    
    def __init__(self, s1_parser: Any = None) -> None:
        """初始化处理器.
        
        Args:
            s1_parser: S-1解析器实例
        """
        self.s1_parser = s1_parser
        self.logger = logging.getLogger(__name__)
    
    def on_new_s1(self, filing: dict) -> None:
        """处理新的S-1文件."""
        self.logger.info(f"New S-1 filed: {filing.get('company_name')} ({filing.get('cik')})")
        
        # 可以在这里触发下载和解析
        if self.s1_parser:
            try:
                # TODO: 下载并解析S-1文件
                pass
            except Exception as e:
                self.logger.error(f"Failed to parse S-1: {e}")
    
    def on_new_424b4(self, filing: dict) -> None:
        """忽略424B4文件."""
        pass


class EdgarIPOCrawler(BaseCrawler):
    """基于EDGAR的IPO爬虫.
    
    从EDGAR获取IPO相关信息，作为Nasdaq的备用/补充。
    """
    
    def __init__(self, db_manager: Any = None) -> None:
        """初始化."""
        super().__init__(
            name="edgar_ipo",
            rate_limit=5.0,
            db_manager=db_manager,
        )
        self.monitor = EdgarMonitor(db_manager)
    
    def fetch(self, **kwargs: Any) -> list[IPOEvent]:
        """从EDGAR获取IPO事件.
        
        通过查询S-1文件获取即将上市的IPO。
        """
        days = kwargs.get("days", 30)
        
        # 获取最近的S-1文件
        s1_filings = self.monitor.get_s1_filings(days=days)
        
        # 转换为IPOEvent（部分信息需要从S-1解析获取）
        events: list[IPOEvent] = []
        for filing in s1_filings:
            event = self._filing_to_event(filing)
            if event:
                events.append(event)
        
        return events
    
    def _filing_to_event(self, filing: dict) -> Optional[IPOEvent]:
        """将S-1文件信息转换为IPOEvent.
        
        注意：此方法只创建基本信息，完整信息需要解析S-1文件。
        """
        try:
            filed_date = None
            if filing.get("filed_date"):
                try:
                    filed_date = datetime.strptime(
                        filing["filed_date"],
                        "%Y-%m-%d"
                    ).date()
                except ValueError:
                    pass
            
            event = IPOEvent(
                cik=filing.get("cik"),
                company_name=filing.get("company_name", ""),
                status=IPOStatus.FILED,
                expected_date=filed_date,
                s1_filing_url=filing.get("filing_url"),
            )
            
            return event
            
        except Exception as e:
            logger.warning(f"Failed to convert filing to event: {e}")
            return None
