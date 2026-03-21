# IPO-Radar 知识库

> 记录 API 文档、架构逻辑、技术选型等关键信息

---

## 数据源 API

### SEC EDGAR

**EDGAR EFTS API**
```
URL: https://efts.sec.gov/LATEST/search-index
Params:
  - q: 搜索查询 (e.g., "S-1")
  - forms: 表单类型 (e.g., "S-1")
  - dateRange: 日期范围
```

**限制**: 10次/秒，必须包含 User-Agent 邮箱

### Nasdaq IPO Calendar

```
URL: https://api.nasdaq.com/api/ipo/calendar
Method: GET
Headers: 需要模拟浏览器 User-Agent
```

### Yahoo Finance (yfinance)

```python
import yfinance as yf

# 获取日线数据
ticker = yf.Ticker("AAPL")
hist = ticker.history(period="1y")

# 获取财报日期
calendar = ticker.calendar
```

### Reddit API

```
限制: 60次/分钟
需要 OAuth 认证
Endpoint: https://oauth.reddit.com/r/stocks/search
```

---

## 技术选型

| 组件 | 选择 | 理由 |
|-----|------|------|
| HTTP Client | httpx + requests | 异步+同步备用 |
| HTML Parser | BeautifulSoup4 + lxml | 成熟稳定 |
| Database | SQLite (dev) / PostgreSQL (prod) | 轻量+可扩展 |
| ORM | SQLAlchemy 2.0 | 标准选择 |
| Scheduler | schedule | 简单够用 |
| Dashboard | Streamlit | 快速开发 |
| LLM | Ollama (本地) | 免费+隐私 |

---

## 关键算法参考

### 指数退避重试

```python
delay = initial_delay * (backoff ** attempt)
```

### 令牌桶限流

- 桶容量: burst
-  refill rate: rate per second

### RSI 计算

```
RSI = 100 - (100 / (1 + RS))
RS = 平均上涨 / 平均下跌
```

### VWAP 计算

```
VWAP = Σ(典型价格 × 成交量) / Σ(成交量)
典型价格 = (High + Low + Close) / 3
```

---

## 形态识别参考

### IPO底部特征 (William O'Neil)

- 深度: 10-35%
- 时间: 7-65周（大型底部）或 5-7周（平底）
- 成交量: 底部缩量，突破放量
- 相对强度: 强于大盘

### 突破确认条件

1. 价格突破左侧高点
2. 成交量 > 1.5x 平均
3. RSI 50-70（不超买）

---

## 股票代码参考 (测试用)

| 代码 | 公司 | IPO日期 | 特征 |
|-----|------|---------|------|
| CAVA | Cava Group | 2023-06-15 | 典型IPO底部突破 |
| ARM | Arm Holdings | 2023-09-14 | 大型IPO |
| RDDT | Reddit | 2024-03-21 | 近期IPO |
| BIRK | Birkenstock | 2023-10-11 | 破发后表现 |

---

## 承销商排名 (2023-2024)

1. Goldman Sachs
2. Morgan Stanley
3. J.P. Morgan
4. Bank of America
5. Citigroup
6. Credit Suisse
7. Barclays
8. UBS
9. Deutsche Bank
10. Wells Fargo
