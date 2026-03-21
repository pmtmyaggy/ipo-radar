# IPO-Radar API 文档

## 核心模块

### CrawlerAPI

爬虫API接口，用于获取市场数据。

```python
from src.crawler.api import CrawlerAPI

api = CrawlerAPI()
```

#### 方法

**`get_latest_price(ticker: str) -> float`**
获取股票最新价格。

**`get_stock_bars(ticker: str, start: date, end: date) -> List[StockBar]`**
获取股票K线数据。

**`refresh_ipo_calendar() -> List[IPOEvent]`**
刷新IPO日历。

---

### IPORadar

IPO雷达监控器。

```python
from src.radar.monitor import IPORadar

radar = IPORadar()
```

#### 方法

**`get_watchlist() -> List[IPOStatus]`**
获取观察名单。

**`get_active_tickers() -> List[str]`**
获取活跃股票代码列表。

**`add_to_watchlist(ticker: str) -> bool`**
添加股票到观察名单。

---

### FundamentalScreener

基本面筛选器。

```python
from src.screener.fundamentals import FundamentalScreener

screener = FundamentalScreener()
```

#### 方法

**`score_ipo(ticker: str) -> QuickScore`**
对IPO进行基本面评分。

**`screen(tickers: List[str], criteria: ScreenCriteria) -> List[str]`**
根据条件筛选股票。

**`batch_score(tickers: List[str]) -> List[QuickScore]`**
批量评分并排序。

---

### SignalAggregator

信号聚合器，生成综合报告。

```python
from src.scorer.composite import SignalAggregator

aggregator = SignalAggregator()
```

#### 方法

**`generate_report(ticker: str) -> CompositeReport`**
生成综合报告。

**示例：**
```python
report = aggregator.generate_report("CAVA")
print(report.overall_signal)  # STRONG_OPPORTUNITY / OPPORTUNITY / WATCH / NO_ACTION
print(report.fundamental_score)  # 0-100
print(report.signal_reasons)  # 信号原因列表
```

---

### DailyScanner

每日扫描器。

```python
from src.scorer.daily_scan import DailyScanner

scanner = DailyScanner()
result = scanner.run_scan()
```

#### 方法

**`run_scan(tickers: Optional[List[str]]) -> ScanResult`**
运行每日扫描。

**`generate_summary_text(result: ScanResult) -> str`**
生成文本摘要报告。

**`get_alerts(result: ScanResult) -> List[dict]`**
获取告警列表。

---

### FeishuNotifier

飞书通知器。

```python
from src.notifier import FeishuNotifier

notifier = FeishuNotifier(webhook_url="https://...")
```

#### 方法

**`send_strong_opportunity_alert(report: dict) -> bool`**
发送强烈机会告警。

**`send_breakout_alert(report: dict) -> bool`**
发送突破信号告警。

**`send_lockup_warning(ticker: str, days_until: int, impact_pct: float) -> bool`**
发送禁售期警告。

**`send_daily_summary(result: ScanResult) -> bool`**
发送每日摘要。

---

## 数据模型

### QuickScore

基本面快速评分结果。

```python
class QuickScore(BaseModel):
    ticker: str
    total: int          # 总分0-100
    details: dict       # 各项得分
    verdict: str        # PASS / FAIL / REVIEW
```

### CompositeReport

综合报告。

```python
class CompositeReport(BaseModel):
    ticker: str
    company_name: Optional[str]
    ipo_date: Optional[date]
    current_price: Optional[float]
    fundamental_score: int
    overall_signal: OverallSignal
    signal_reasons: List[str]
    risk_factors: List[str]
    windows: WindowsStatus
```

### WindowsStatus

四窗口状态。

```python
class WindowsStatus(BaseModel):
    first_day_pullback: FirstDayPullbackWindow
    ipo_base_breakout: IPOBaseBreakoutWindow
    lockup_expiry: LockupExpiryWindow
    first_earnings: FirstEarningsWindow
```

---

## 命令行接口

### 评分器CLI

```bash
# 分析单个股票
python -m src.scorer --ticker CAVA

# 运行每日扫描
python -m src.scorer --scan --save
```

### Makefile 命令

```bash
make install      # 安装依赖
make setup        # 初始化项目
make test         # 运行测试
make dashboard    # 启动仪表盘
make scan         # 运行扫描
make scheduler    # 启动定时任务
make start        # Docker启动所有服务
make stop         # Docker停止服务
```

---

## 信号说明

### OverallSignal 枚举

- **STRONG_OPPORTUNITY**: 强烈机会，建议买入
- **OPPORTUNITY**: 有机会，可考虑买入
- **WATCH**: 观察中，等待更好时机
- **NO_ACTION**: 无操作，暂不考虑

### 信号触发条件

**STRONG_OPPORTUNITY:**
- 任一窗口强信号 + 基本面>=60 + 情绪>=0.3

**OPPORTUNITY:**
- 任一窗口有信号 + 基本面>=50

**WATCH:**
- 底部形成中
- 禁售期14天内到期

---

## 配置项

### 环境变量

| 变量名 | 说明 | 必需 |
|--------|------|------|
| `EDGAR_IDENTITY` | SEC EDGAR API身份 | 是 |
| `FEISHU_WEBHOOK_URL` | 飞书通知URL | 否 |
| `OPENAI_API_KEY` | OpenAI API密钥 | 否 |
| `DATABASE_URL` | 数据库连接URL | 否 |
| `LOG_LEVEL` | 日志级别 | 否 |

---

## 错误处理

所有API可能抛出以下异常：

- `ValueError`: 参数错误
- `ConnectionError`: 网络连接失败
- `TimeoutError`: 请求超时

建议使用try-except块处理：

```python
try:
    report = aggregator.generate_report("CAVA")
except Exception as e:
    logger.error(f"Failed to generate report: {e}")
```
