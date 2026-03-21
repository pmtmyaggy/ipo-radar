"""飞书通知模块 - 发送关键信号通知."""

import json
import logging
import os
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class FeishuNotifier:
    """飞书通知器.
    
    使用飞书Webhook机器人发送通知。
    """
    
    def __init__(self, webhook_url: Optional[str] = None):
        """初始化通知器.
        
        Args:
            webhook_url: 飞书Webhook URL，默认从环境变量获取
        """
        self.webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)
        self.logger = logging.getLogger(__name__)
    
    def send_message(self, title: str, content: str, msg_type: str = "text") -> bool:
        """发送消息.
        
        Args:
            title: 消息标题
            content: 消息内容
            msg_type: 消息类型 (text/markdown)
        
        Returns:
            是否发送成功
        """
        if not self.enabled:
            self.logger.warning("Feishu notifier not enabled (no webhook URL)")
            return False
        
        try:
            if msg_type == "markdown":
                payload = {
                    "msg_type": "interactive",
                    "card": {
                        "header": {
                            "title": {
                                "tag": "plain_text",
                                "content": title,
                            },
                            "template": "blue",
                        },
                        "elements": [
                            {
                                "tag": "div",
                                "text": {
                                    "tag": "lark_md",
                                    "content": content,
                                },
                            }
                        ],
                    },
                }
            else:
                payload = {
                    "msg_type": "text",
                    "content": {
                        "text": f"{title}\n\n{content}",
                    },
                }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get("code") == 0:
                self.logger.info(f"Message sent successfully: {title}")
                return True
            else:
                self.logger.error(f"Failed to send message: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            return False
    
    def send_strong_opportunity_alert(self, report: dict) -> bool:
        """发送强烈机会告警.
        
        Args:
            report: 股票报告字典
        """
        ticker = report['ticker']
        company = report.get('company_name', ticker)
        
        title = f"🚨 STRONG OPPORTUNITY: {ticker}"
        
        content = f"""
**{company} ({ticker})** 触发强烈买入信号！

📊 **关键指标:**
• 当前价: ${report.get('current_price', 'N/A')}
• vs IPO: {((report.get('price_vs_ipo', 1) - 1) * 100):+.1f}%
• 基本面评分: {report.get('fundamental_score', 'N/A')}/100

🎯 **信号原因:**
"""
        
        for reason in report.get('signal_reasons', []):
            content += f"• {reason}\n"
        
        if report.get('risk_factors'):
            content += "\n⚠️ **风险提示:**\n"
            for risk in report.get('risk_factors', [])[:3]:
                content += f"• {risk}\n"
        
        content += f"\n⏰ 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        return self.send_message(title, content, msg_type="markdown")
    
    def send_breakout_alert(self, report: dict) -> bool:
        """发送突破信号告警."""
        ticker = report['ticker']
        
        title = f"📈 突破信号: {ticker}"
        
        content = f"""
**{ticker}** 确认IPO底部突破！

📊 **突破详情:**
• 当前价: ${report.get('current_price', 'N/A')}
• 突破强度: {report.get('windows', {}).get('breakout_signal', 'unknown')}

⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        
        return self.send_message(title, content, msg_type="markdown")
    
    def send_lockup_warning(self, ticker: str, days_until: int, impact_pct: float) -> bool:
        """发送禁售期预警.
        
        Args:
            ticker: 股票代码
            days_until: 距离到期天数
            impact_pct: 供应冲击比例
        """
        if days_until <= 3:
            title = f"🔴 紧急: {ticker} 禁售期即将到期"
            urgency = "紧急"
        else:
            title = f"🟡 预警: {ticker} 禁售期即将到期"
            urgency = "预警"
        
        content = f"""
**{ticker}** 禁售期到期{urgency}！

🔒 **关键信息:**
• 到期时间: {days_until}天后
• 供应冲击: {impact_pct:.1%} 流通股
• 可能影响: {'高' if impact_pct > 0.3 else '中' if impact_pct > 0.1 else '低'}

⚠️ 注意股价波动风险！
"""
        
        return self.send_message(title, content, msg_type="markdown")
    
    def send_earnings_reminder(self, ticker: str, days_until: int) -> bool:
        """发送财报提醒."""
        title = f"📊 财报提醒: {ticker}"
        
        content = f"""
**{ticker}** 即将发布首次财报！

📅 **详情:**
• 发布时间: {days_until}天后
• 类型: 首次公开财报 (IPO后首份)

⚠️ 注意：首次财报通常会引起较大波动
"""
        
        return self.send_message(title, content, msg_type="markdown")
    
    def send_daily_summary(self, result) -> bool:
        """发送每日扫描摘要.
        
        Args:
            result: ScanResult对象
        """
        title = f"📊 IPO-Radar 每日扫描报告 ({result.scanned_at.strftime('%Y-%m-%d')})"
        
        content = f"""
**扫描概览:**
• 扫描股票数: {result.total_count}
• 🎯 强烈机会: {result.strong_opportunity_count}
• 📈 有机会: {result.opportunity_count}
• 👀 观察: {result.watch_count}
• ➖ 无操作: {result.no_action_count}

"""
        
        # 添加强烈机会列表
        if result.strong_opportunity_count > 0:
            content += "**🔥 强烈机会股票:**\n"
            for report in result.reports:
                if report.get('overall_signal') == 'STRONG_OPPORTUNITY':
                    content += f"• {report['ticker']}: {report.get('signal_reasons', [''])[0]}\n"
        
        if result.errors:
            content += f"\n⚠️ 错误: {len(result.errors)}个"
        
        return self.send_message(title, content, msg_type="markdown")


class NotificationManager:
    """通知管理器.
    
    统一管理所有通知触发逻辑。
    """
    
    def __init__(self, notifier: Optional[FeishuNotifier] = None):
        """初始化."""
        self.notifier = notifier or FeishuNotifier()
        self.logger = logging.getLogger(__name__)
    
    def process_scan_result(self, result) -> None:
        """处理扫描结果，发送必要通知.
        
        Args:
            result: ScanResult对象
        """
        if not self.notifier.enabled:
            return
        
        # 发送每日摘要
        self.notifier.send_daily_summary(result)
        
        # 发送强烈机会告警
        for report in result.reports:
            if report.get('overall_signal') == 'STRONG_OPPORTUNITY':
                self.notifier.send_strong_opportunity_alert(report)
            
            # 检查禁售期紧急告警
            windows = report.get('windows', {})
            if windows.get('lockup_days_until') is not None:
                days = windows['lockup_days_until']
                if days <= 3:
                    self.notifier.send_lockup_warning(
                        report['ticker'],
                        days,
                        windows.get('supply_impact_pct', 0),
                    )


def test_notifier():
    """测试通知器."""
    notifier = FeishuNotifier()
    
    test_report = {
        "ticker": "TEST",
        "company_name": "Test Company",
        "current_price": 25.5,
        "price_vs_ipo": 1.15,
        "fundamental_score": 75,
        "overall_signal": "STRONG_OPPORTUNITY",
        "signal_reasons": ["测试信号"],
        "windows": {},
    }
    
    notifier.send_strong_opportunity_alert(test_report)


if __name__ == "__main__":
    test_notifier()
