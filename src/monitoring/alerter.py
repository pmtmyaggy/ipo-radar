"""告警系统.

PRD 6.2: 当任何模块超过2小时未成功运行，自动发送飞书告警。
"""

import logging
import os
from datetime import datetime
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)


class FeishuAlerter:
    """飞书告警器."""
    
    def __init__(self, webhook_url: Optional[str] = None):
        """初始化.
        
        Args:
            webhook_url: 飞书Webhook URL，默认从环境变量获取
        """
        self.webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)
        self.logger = logging.getLogger(__name__)
    
    def send_alert(self, title: str, content: str, level: str = "warning") -> bool:
        """发送告警.
        
        Args:
            title: 告警标题
            content: 告警内容
            level: 告警级别 (warning/error/info)
            
        Returns:
            是否发送成功
        """
        if not self.enabled:
            self.logger.warning(f"Feishu alerter not enabled. Alert: {title}")
            return False
        
        # 根据级别设置颜色
        color_map = {
            "info": "blue",
            "warning": "orange",
            "error": "red",
        }
        color = color_map.get(level, "red")
        
        # 构建消息卡片
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"🚨 {title}",
                    },
                    "template": color,
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": content,
                        },
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                            }
                        ],
                    },
                ],
            },
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get("code") == 0:
                self.logger.info(f"Alert sent: {title}")
                return True
            else:
                self.logger.error(f"Failed to send alert: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending alert: {e}")
            return False


class AlertManager:
    """告警管理器.
    
    监控爬虫健康状态，触发告警。
    
    PRD 6.2: 2小时未运行自动告警。
    """
    
    def __init__(self, monitor=None, alerter: Optional[FeishuAlerter] = None):
        """初始化.
        
        Args:
            monitor: 监控器实例
            alerter: 告警器实例
        """
        from .monitor import get_monitor
        
        self.monitor = monitor or get_monitor()
        self.alerter = alerter or FeishuAlerter()
        self.logger = logging.getLogger(__name__)
    
    def check_and_alert(self) -> bool:
        """检查健康状态并发送告警.
        
        Returns:
            是否触发了告警
        """
        issues = self.monitor.check_health()
        alert_triggered = False
        
        # 检查不健康的爬虫（2小时未运行）
        for crawler_name in issues['unhealthy_crawlers']:
            alert_key = f"crawler_{crawler_name}"
            
            if self.monitor.should_alert(alert_key, cooldown_minutes=120):
                success = self.alerter.send_alert(
                    title=f"爬虫异常: {crawler_name}",
                    content=f"爬虫 **{crawler_name}** 超过2小时未成功运行。\n\n请检查：\n- 数据源是否正常\n- 网络连接\n- 爬虫日志",
                    level="error",
                )
                if success:
                    alert_triggered = True
        
        # 检查过时的数据表
        for table_name in issues['stale_tables']:
            alert_key = f"table_{table_name}"
            
            if self.monitor.should_alert(alert_key, cooldown_minutes=120):
                success = self.alerter.send_alert(
                    title=f"数据表过时: {table_name}",
                    content=f"数据表 **{table_name}** 超过2小时未更新。\n\n可能原因：\n- 爬虫未运行\n- 数据处理异常\n- 数据库连接问题",
                    level="warning",
                )
                if success:
                    alert_triggered = True
        
        return alert_triggered
    
    def send_daily_summary(self) -> bool:
        """发送每日监控摘要.
        
        Returns:
            是否发送成功
        """
        report = self.monitor.generate_report()
        
        return self.alerter.send_alert(
            title="IPO-Radar 每日监控报告",
            content=report,
            level="info",
        )
    
    def send_test_alert(self) -> bool:
        """发送测试告警.
        
        Returns:
            是否发送成功
        """
        return self.alerter.send_alert(
            title="测试告警",
            content="这是IPO-Radar监控系统的测试告警。\n\n如果收到此消息，说明告警系统配置正确。",
            level="info",
        )


# 便捷函数
def get_alert_manager() -> AlertManager:
    """获取告警管理器实例."""
    return AlertManager()
