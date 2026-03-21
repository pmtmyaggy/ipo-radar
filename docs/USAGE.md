# IPO-Radar 使用手册

## 目录

1. [快速开始](#快速开始)
2. [命令行工具](#命令行工具)
3. [仪表盘使用](#仪表盘使用)
4. [API使用示例](#api使用示例)
5. [信号解读](#信号解读)
6. [常见问题](#常见问题)

---

## 快速开始

### 启动系统

```bash
# 方法1: 本地启动
cd ipo-radar
make dashboard

# 方法2: Docker启动
make start
```

访问 http://localhost:8501 查看仪表盘。

---

## 命令行工具

### 分析单个股票

```bash
python -m src.scorer --ticker CAVA
```

输出示例：
```
🚀 IPO-Radar 分析结果: CAVA
================================
📊 综合评分: 75/100
🎯 信号: OPPORTUNITY
📈 当前价: $52.30 (+15% vs IPO)

信号原因:
• IPO底部强势突破确认
• 基本面评分较高

风险因素:
• 禁售期即将到期，解锁股份占流通股15%
```

### 运行每日扫描

```bash
# 仅显示结果
make scan

# 保存报告
python -m src.scorer --scan --save
```

### 管理观察名单

```bash
# 查看观察名单
python -m src.radar --list

# 添加股票
python -m src.radar --add CAVA

# 移除股票
python -m src.radar --remove CAVA
```

---

## 仪表盘使用

### 主页 - 信号总览

仪表盘主页显示所有观察股票的信号概览：

| 列名 | 说明 |
|------|------|
| 股票 | 股票代码 |
| 公司 | 公司名称 |
| 信号 | 综合信号强度 |
| 基本面 | 基本面评分 (0-100) |
| 当前价 | 最新价格 |
| 操作 | 查看详情/移除 |

**信号颜色说明：**
- 🟢 **绿色**: STRONG_OPPORTUNITY (强烈机会)
- 🔵 **蓝色**: OPPORTUNITY (有机会)
- 🟡 **黄色**: WATCH (观察中)
- ⚪ **灰色**: NO_ACTION (无操作)

### 个股详情页

点击股票进入详情页，包含：

1. **K线图**
   - 紫色线: IPO发行价
   - 绿色区域: 底部形态区间
   - 红色点: 突破信号点
   - 橙色线: 禁售期到期日

2. **四窗口状态卡**
   - 首日回调窗口
   - IPO底部突破窗口
   - 禁售期到期窗口
   - 首次财报窗口

3. **基本面雷达图**
   - 营收增速
   - 毛利率
   - 现金跑道
   - 债务水平
   - 市值规模

4. **最近新闻**
   - 显示最近7天相关新闻
   - 情绪标记 (正面/负面)

### IPO日历页

包含三个标签页：

**即将上市**: 未来30天内计划IPO的公司
**即将到期禁售期**: 未来30天内禁售期到期的股票
**即将发布财报**: 未来30天内发布财报的公司

---

## API使用示例

### Python API

```python
from src.scorer.composite import SignalAggregator
from src.scorer.daily_scan import DailyScanner
from src.radar.monitor import IPORadar

# 1. 分析单个股票
aggregator = SignalAggregator()
report = aggregator.generate_report("CAVA")

print(f"信号: {report.overall_signal}")
print(f"评分: {report.fundamental_score}/100")
print(f"原因: {report.signal_reasons}")

# 2. 运行每日扫描
scanner = DailyScanner()
result = scanner.run_scan()

# 获取强烈机会股票
strong_opportunities = [
    r for r in result.reports 
    if r['overall_signal'] == 'STRONG_OPPORTUNITY'
]

# 3. 管理观察名单
radar = IPORadar()
radar.add_to_watchlist("CAVA")
watchlist = radar.get_watchlist()
```

### 批量处理

```python
from src.utils.batch_processor import batch_process, memory_efficient_scan

# 批量评分
scores = list(batch_process(
    tickers, 
    batch_size=50,
    processor=score_batch
))

# 内存高效扫描
for report in memory_efficient_scan(tickers, aggregator.generate_report):
    process_report(report)
```

---

## 信号解读

### 信号类型

| 信号 | 含义 | 建议操作 |
|------|------|----------|
| **STRONG_OPPORTUNITY** | 强烈买入信号，多重窗口确认 | 建议买入 |
| **OPPORTUNITY** | 有机会，单一窗口确认 | 可考虑买入 |
| **WATCH** | 观察中，等待更好时机 | 持续关注 |
| **NO_ACTION** | 暂无明显信号 | 暂不关注 |

### 触发条件

**STRONG_OPPORTUNITY:**
- 任一窗口强信号
- 基本面评分 >= 60
- 情绪评分 >= 0.3

**OPPORTUNITY:**
- 任一窗口有信号
- 基本面评分 >= 50

**WATCH:**
- 底部形态形成中
- 或禁售期14天内到期

### 四窗口说明

**1. 首日回调窗口 (First Day Pullback)**
- 时间: IPO后1-5天
- 信号: 破发后反弹至IPO价之上

**2. IPO底部突破窗口 (IPO Base Breakout)**
- 时间: IPO后2-12周
- 信号: 突破底部高点 + 成交量确认

**3. 禁售期到期窗口 (Lockup Expiry)**
- 时间: 禁售期到期前后
- 信号: 到期前卖出，到期后买入

**4. 首次财报窗口 (First Earnings)**
- 时间: IPO后首次财报
- 信号: EPS/Revenue超预期

---

## 常见问题

### Q: 如何添加新的股票到监控？

```bash
# 方法1: CLI
python -m src.radar --add TICKER

# 方法2: 仪表盘
在侧边栏输入股票代码，点击"添加"
```

### Q: 数据源更新频率？

| 数据类型 | 更新频率 | 说明 |
|----------|----------|------|
| 价格 | 实时 | 盘中每15分钟 |
| 基本面 | 每日 | 盘前更新 |
| 新闻 | 每小时 | 自动抓取 |
| 财报 | 每日 | 盘前检查 |

### Q: 如何配置飞书通知？

```bash
# 1. 在.env中配置
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx

# 2. 测试通知
python -c "from src.notifier import FeishuNotifier; FeishuNotifier().send_message('Test', 'Hello')"
```

### Q: 数据库在哪里？

```
data/
└── ipo_radar.db          # SQLite数据库
└── backups/              # 自动备份
```

### Q: 如何备份数据？

```bash
# 手动备份
make backup

# 自动备份 (添加到crontab)
0 2 * * * cd /path/to/ipo-radar && make backup
```

### Q: 出现内存错误怎么办？

```python
# 减少批次大小
from src.utils.batch_processor import batch_process

results = list(batch_process(
    tickers,
    batch_size=25,  # 减小批次
    enable_gc=True,  # 启用垃圾回收
))
```

### Q: 如何更新数据库结构？

```bash
# 使用Alembic迁移
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

---

## 高级用法

### 自定义筛选条件

```python
from src.screener.fundamentals import FundamentalScreener, ScreenCriteria

screener = FundamentalScreener()

criteria = ScreenCriteria(
    min_revenue_growth=0.20,
    min_gross_margin=0.50,
    min_market_cap=1_000_000_000,
)

passed = screener.screen(tickers, criteria)
```

### 情绪分析增强

```python
from src.sentiment.analyzer import SentimentAnalyzer

# 启用Ollama增强 (需要本地Ollama服务)
analyzer = SentimentAnalyzer(use_ollama=True)
result = analyzer.analyze("CAVA", days=7)
```

### 自定义通知规则

```python
from src.notifier import NotificationManager, FeishuNotifier

notifier = FeishuNotifier()
manager = NotificationManager(notifier=notifier)

# 自定义处理逻辑
def custom_processor(result):
    for report in result.reports:
        if report['fundamental_score'] > 80:
            notifier.send_strong_opportunity_alert(report)

manager.process_scan_result = custom_processor
```

---

## 故障排除

### 仪表盘无法启动

```bash
# 检查端口占用
lsof -i :8501

# 检查依赖
pip install -r requirements.txt

# 检查数据库
make setup
```

### 数据不更新

```bash
# 检查数据源连接
python -m src.crawler --test

# 手动刷新
python -m src.crawler --refresh

# 检查日志
tail -f logs/ipo_radar.log
```

### 扫描结果不准确

1. 检查基本面数据是否最新
2. 确认IPO日期正确
3. 检查是否有足够的K线数据
4. 查看 `windows` 字段的详细状态

---

## 相关链接

- [部署指南](DEPLOYMENT.md)
- [API文档](API.md)
- [GitHub Issues](https://github.com/your-repo/ipo-radar/issues)

---

**需要帮助？** 请在 GitHub Issues 提交问题或联系维护团队。
