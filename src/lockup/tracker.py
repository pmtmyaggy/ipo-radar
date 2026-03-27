"""禁售期跟踪模块 - 监控内部人士和机构的禁售期到期日."""

import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from src.crawler.api import CrawlerAPI
from src.crawler.models.schemas import LockupInfo, LockupStatus
from src.crawler.models.database import DatabaseManager

logger = logging.getLogger(__name__)


class LockupTracker:
    """禁售期跟踪器.

    监控禁售期到期日，评估供应冲击。
    """

    WARNING_DAYS = 14  # 14天预警
    IMMINENT_DAYS = 3  # 3天紧急
    HIGH_IMPACT_PCT = 0.30  # 30%以上供应冲击为高影响

    def __init__(
        self,
        crawler: Optional[CrawlerAPI] = None,
        db_manager: Optional[DatabaseManager] = None,
    ):
        """初始化."""
        self.crawler = crawler or CrawlerAPI()
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)

    def get_lockup_info(self, ticker: str) -> Optional[LockupInfo]:
        """获取禁售期信息."""
        # 尝试从数据库获取
        if self.db_manager:
            from src.crawler.models.database import LockupInfoModel

            with self.db_manager.session_scope() as session:
                result = session.query(LockupInfoModel).filter_by(ticker=ticker).first()

                if result:
                    if not (
                        result.ticker
                        and result.ipo_date
                        and result.lockup_days
                        and result.lockup_expiry_date
                    ):
                        return None

                    raw_locked_holders: list[str] | str = result.locked_holders or []
                    locked_holders: list[str]
                    if isinstance(raw_locked_holders, str):
                        try:
                            parsed = json.loads(raw_locked_holders)
                            locked_holders = (
                                [str(holder) for holder in parsed]
                                if isinstance(parsed, list)
                                else []
                            )
                        except json.JSONDecodeError:
                            locked_holders = [
                                holder.strip()
                                for holder in raw_locked_holders.split(",")
                                if holder.strip()
                            ]
                    else:
                        locked_holders = raw_locked_holders

                    return LockupInfo(
                        ticker=result.ticker,
                        ipo_date=result.ipo_date,
                        lockup_days=result.lockup_days,
                        lockup_expiry_date=result.lockup_expiry_date,
                        shares_locked=result.shares_locked,
                        locked_holders=locked_holders,
                        early_release_provisions=result.early_release_provisions or False,
                        total_shares_outstanding=result.total_shares_outstanding,
                        float_after_ipo=result.float_after_ipo,
                        float_after_lockup=result.float_after_lockup,
                        supply_impact_pct=(
                            Decimal(str(result.supply_impact_pct))
                            if result.supply_impact_pct is not None
                            else None
                        ),
                        status=self._calculate_status(result.lockup_expiry_date),
                    )

        return None

    def _calculate_status(self, expiry_date: date) -> LockupStatus:
        """计算禁售期状态."""
        today = date.today()
        days_until = (expiry_date - today).days

        if days_until < 0:
            return LockupStatus.EXPIRED
        elif days_until <= self.IMMINENT_DAYS:
            return LockupStatus.IMMINENT
        elif days_until <= self.WARNING_DAYS:
            return LockupStatus.WARNING
        else:
            return LockupStatus.ACTIVE

    def get_upcoming_expiries(
        self,
        days_ahead: int = 30,
        min_impact_pct: float = 0.10,
    ) -> list[LockupInfo]:
        """获取即将到期的禁售期."""
        today = date.today()
        cutoff = today + timedelta(days=days_ahead)

        events = []

        if self.db_manager:
            from src.crawler.models.database import LockupInfoModel

            with self.db_manager.session_scope() as session:
                results = (
                    session.query(LockupInfoModel)
                    .filter(
                        LockupInfoModel.lockup_expiry_date >= today,
                        LockupInfoModel.lockup_expiry_date <= cutoff,
                    )
                    .all()
                )

                for result in results:
                    if not (
                        result.ticker
                        and result.ipo_date
                        and result.lockup_days
                        and result.lockup_expiry_date
                    ):
                        continue

                    info = LockupInfo(
                        ticker=result.ticker,
                        ipo_date=result.ipo_date,
                        lockup_days=result.lockup_days,
                        lockup_expiry_date=result.lockup_expiry_date,
                        supply_impact_pct=(
                            Decimal(str(result.supply_impact_pct))
                            if result.supply_impact_pct is not None
                            else None
                        ),
                        status=self._calculate_status(result.lockup_expiry_date),
                    )

                    # 过滤低影响
                    if info.supply_impact_pct and info.supply_impact_pct >= Decimal(
                        str(min_impact_pct)
                    ):
                        events.append(info)

        # 按到期日排序
        events.sort(key=lambda x: x.lockup_expiry_date)

        return events

    def estimate_price_impact(self, supply_impact_pct: float, holder_types: list) -> str:
        """预估价格影响."""
        if supply_impact_pct > self.HIGH_IMPACT_PCT or any(h in holder_types for h in ["vc", "pe"]):
            return "high"
        elif supply_impact_pct > 0.10:
            return "medium"
        else:
            return "low"


class LockupCalendar:
    """禁售期日历."""

    def __init__(self, tracker: LockupTracker):
        self.tracker = tracker

    def get_calendar_by_month(self, year: int, month: int) -> list[LockupInfo]:
        """获取指定月份的禁售期日历."""
        from calendar import monthrange

        _, last_day = monthrange(year, month)
        start = date(year, month, 1)
        end = date(year, month, last_day)

        all_events = self.tracker.get_upcoming_expiries(days_ahead=365)

        return [e for e in all_events if start <= e.lockup_expiry_date <= end]
