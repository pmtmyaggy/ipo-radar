"""定时任务调度器.

使用schedule库设置定时任务：
- 每日盘前8:30 EST: 运行daily_scan
- 每15分钟(盘中): 检查突破信号
- 每日盘后: 更新形态分析
- 每周日: 更新IPO日历和禁售期日历
"""

import logging
import time
from datetime import datetime
from typing import Callable, Optional

import schedule

from src.scorer.daily_scan import DailyScanner
from src.radar.monitor import IPORadar
from src.crawler.api import CrawlerAPI
from src.notifier import NotificationManager

logger = logging.getLogger(__name__)


class TaskScheduler:
    """任务调度器.
    
    管理所有定时任务的调度。
    """
    
    def __init__(
        self,
        scanner: Optional[DailyScanner] = None,
        radar: Optional[IPORadar] = None,
        notifier: Optional[NotificationManager] = None,
    ):
        """初始化调度器."""
        self.scanner = scanner or DailyScanner()
        self.radar = radar or IPORadar()
        self.notifier = notifier or NotificationManager()
        
        self.logger = logging.getLogger(__name__)
        self._running = False
    
    def setup_daily_scan(self, time_str: str = "08:30") -> None:
        """设置每日扫描任务.
        
        Args:
            time_str: 时间字符串，如 "08:30"
        """
        schedule.every().day.at(time_str).do(self._run_daily_scan)
        self.logger.info(f"Daily scan scheduled at {time_str}")
    
    def _run_daily_scan(self) -> None:
        """运行每日扫描."""
        self.logger.info("Running scheduled daily scan")
        
        try:
            result = self.scanner.run_scan()
            
            # 处理通知
            self.notifier.process_scan_result(result)
            
            self.logger.info("Daily scan completed")
            
        except Exception as e:
            self.logger.error(f"Daily scan failed: {e}")
    
    def setup_intraday_check(self, interval_minutes: int = 15) -> None:
        """设置盘中检查任务.
        
        Args:
            interval_minutes: 检查间隔（分钟）
        """
        schedule.every(interval_minutes).minutes.do(self._run_intraday_check)
        self.logger.info(f"Intraday check scheduled every {interval_minutes} minutes")
    
    def _run_intraday_check(self) -> None:
        """运行盘中检查."""
        # 只在交易时间运行（9:30-16:00 EST）
        now = datetime.now()
        
        # 简化：假设当前时区是EST
        if not (9 <= now.hour < 16 or (now.hour == 16 and now.minute == 0)):
            return
        
        self.logger.debug("Running intraday breakout check")
        
        try:
            # 获取活跃股票
            tickers = self.radar.get_active_tickers()
            
            # 检查突破（简化实现）
            for ticker in tickers[:10]:  # 只检查前10只
                # TODO: 实现盘中突破检测
                pass
            
        except Exception as e:
            self.logger.error(f"Intraday check failed: {e}")
    
    def setup_post_market_update(self, time_str: str = "16:30") -> None:
        """设置盘后更新任务.
        
        Args:
            time_str: 时间字符串
        """
        schedule.every().day.at(time_str).do(self._run_post_market_update)
        self.logger.info(f"Post-market update scheduled at {time_str}")
    
    def _run_post_market_update(self) -> None:
        """运行盘后更新."""
        self.logger.info("Running post-market update")
        
        try:
            # 更新观察名单状态
            self.radar.run_full_scan()
            
            # 更新形态分析
            tickers = self.radar.get_active_tickers()
            
            self.logger.info(f"Post-market update completed for {len(tickers)} stocks")
            
        except Exception as e:
            self.logger.error(f"Post-market update failed: {e}")
    
    def setup_weekly_update(self, day: str = "sunday", time_str: str = "10:00") -> None:
        """设置每周更新任务.
        
        Args:
            day: 星期几，如 "sunday"
            time_str: 时间字符串
        """
        job = getattr(schedule.every(), day)
        job.at(time_str).do(self._run_weekly_update)
        self.logger.info(f"Weekly update scheduled on {day} at {time_str}")
    
    def _run_weekly_update(self) -> None:
        """运行每周更新."""
        self.logger.info("Running weekly update")
        
        try:
            # 更新IPO日历
            crawler = CrawlerAPI()
            crawler.refresh_ipo_calendar()
            
            # 扫描新IPO
            new_ipos = self.radar.scan_new_ipos()
            
            self.logger.info(f"Weekly update completed, found {len(new_ipos)} new IPOs")
            
        except Exception as e:
            self.logger.error(f"Weekly update failed: {e}")
    
    def start(self) -> None:
        """启动调度器.
        
        警告：此方法会阻塞当前线程！
        建议在后台线程中运行。
        """
        self._running = True
        self.logger.info("Task scheduler started")
        
        while self._running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
            except Exception as e:
                self.logger.error(f"Scheduler error: {e}")
                time.sleep(60)
    
    def stop(self) -> None:
        """停止调度器."""
        self._running = False
        self.logger.info("Task scheduler stopped")
    
    def run_once(self, task_name: str) -> None:
        """手动运行一次指定任务.
        
        Args:
            task_name: 任务名称 (daily_scan/intraday/post_market/weekly)
        """
        tasks = {
            "daily_scan": self._run_daily_scan,
            "intraday": self._run_intraday_check,
            "post_market": self._run_post_market_update,
            "weekly": self._run_weekly_update,
        }
        
        task = tasks.get(task_name)
        if task:
            task()
        else:
            self.logger.error(f"Unknown task: {task_name}")


def start_scheduler_background():
    """在后台线程启动调度器."""
    import threading
    
    scheduler = TaskScheduler()
    
    # 设置任务
    scheduler.setup_daily_scan("08:30")
    scheduler.setup_intraday_check(15)
    scheduler.setup_post_market_update("16:30")
    scheduler.setup_weekly_update("sunday", "10:00")
    
    # 在后台线程启动
    thread = threading.Thread(target=scheduler.start, daemon=True)
    thread.start()
    
    return scheduler


if __name__ == "__main__":
    # 测试调度器
    logging.basicConfig(level=logging.INFO)
    
    scheduler = TaskScheduler()
    scheduler.setup_daily_scan()
    
    print("Scheduler test - running daily scan once...")
    scheduler.run_once("daily_scan")
