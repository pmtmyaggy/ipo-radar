# IPO-Radar 数据源说明

> 详细介绍系统中所有爬虫的数据来源、获取内容和使用限制

---

## 📊 数据源总览

| 数据源 | 网站 | 数据类型 | 频率限制 | 是否必需 |
|--------|------|---------|----------|----------|
| **Yahoo Finance** | finance.yahoo.com | 股价、基本面 | 无明确限制 | ✅ 是 |
| **SEC EDGAR** | sec.gov | S-1招股书、13F持仓 | 10次/秒 | ✅ 是 |
| **Nasdaq** | api.nasdaq.com | IPO日历 | 无明确限制 | ⚠️ 部分 |
| **IPOScoop** | iposcoop.com | IPO日历(备用) | 需遵守robots.txt | ❌ 否 |
| **Benzinga** | benzinga.com | IPO日历 | API需授权 | ❌ 否 |
| **Reddit** | reddit.com | 社交情绪 | API需授权 | ❌ 否 |

---

## 1. Yahoo Finance

### 1.1 基本信息

| 项目 | 内容 |
|------|------|
| **网站** | https://finance.yahoo.com |
| **API** | yfinance (Python库) |
| **数据类型** | 实时股价、历史数据、基本面数据 |
| **更新频率** | 实时 (15分钟延迟) |
| **身份认证** | 无需 |
| **费用** | 免费 |

### 1.2 获取的数据

```python
# 股价数据
- 开盘价 (Open)
- 收盘价 (Close)
- 最高价 (High)
- 最低价 (Low)
- 成交量 (Volume)
- 调整收盘价 (Adj Close)

# 基本面数据
- 市值 (Market Cap)
- 市盈率 (P/E Ratio)
- 营收 (Revenue)
- 净利润 (Net Income)
- 毛利率 (Gross Margin)
- 每股收益 (EPS)

# 财报日期
- 下次财报日期 (Earnings Date)
- 历史财报日期
```

### 1.3 使用场景

- **价格追踪**: 获取IPO后每日股价走势
- **技术分析**: 计算均线、涨跌幅等指标
- **基本面评分**: 获取市值、营收增长率等数据

### 1.4 代码位置

```
src/crawler/yahoo_finance.py
```

### 1.5 限制说明

- 免费版有隐性频率限制（约每秒1-2次）
- 历史财报数据可能不完整
- 部分数据有15分钟延迟

---

## 2. SEC EDGAR

### 2.1 基本信息

| 项目 | 内容 |
|------|------|
| **网站** | https://www.sec.gov/edgar |
| **API** | EDGAR Search API / EFTS API |
| **数据类型** | S-1招股书、13F持仓、10-K/10-Q财报 |
| **更新频率** | 实时（提交后立即公开） |
| **身份认证** | 需要 EDGAR_IDENTITY |
| **费用** | 免费 |

### 2.2 获取的数据

#### S-1 招股书 (Form S-1)

```python
- 公司基本信息
- 发行股数和价格区间
- 募集资金用途
- 财务报表（营收、利润、现金流）
- 风险因素
- 管理层信息
- 股权结构
- 承销商信息
```

#### 13F 机构持仓 (Form 13F)

```python
- 机构名称 (Institution Name)
- 持仓股票 (Holdings)
- 持仓数量 (Shares)
- 持仓市值 (Value)
- 持仓变化（新增/减持/清仓）
- 投资风格分析
```

#### 10-K/10-Q 财报

```python
- 年度/季度财务报表
- 资产负债表
- 利润表
- 现金流量表
- 管理层讨论与分析 (MD&A)
```

### 2.3 API 端点

```
# 搜索API
https://efts.sec.gov/LATEST/search-index

# 文件访问
https://www.sec.gov/Archives/edgar/data/{CIK}/{ACCESSION_NUMBER}/{FILENAME}

# 13F列表
https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=13F
```

### 2.4 使用场景

- **招股书分析**: 深度研究IPO公司基本面
- **机构跟踪**: 跟随聪明钱的投资动向
- **财务分析**: 获取最权威的财务数据

### 2.5 代码位置

```
src/crawler/sec_edgar.py       # 基础EDGAR爬虫
src/crawler/s1_parser.py       # S-1文件解析
src/crawler/holdings_fetcher.py # 13F持仓获取
src/crawler/edgar_monitor.py   # EDGAR实时监控
```

### 2.6 限制说明

- **频率限制**: 每秒不超过10个请求
- **身份要求**: 必须提供 EDGAR_IDENTITY (姓名+邮箱)
- **数据格式**: 多为XML或文本，需要解析

---

## 3. Nasdaq

### 3.1 基本信息

| 项目 | 内容 |
|------|------|
| **网站** | https://www.nasdaq.com/market-activity/ipos |
| **API** | https://api.nasdaq.com/api/ipo/calendar |
| **数据类型** | IPO日历、定价信息 |
| **更新频率** | 每日更新 |
| **身份认证** | 无需 |
| **费用** | 免费 |

### 3.2 获取的数据

```python
# 即将上市的IPO (Upcoming)
- 股票代码 (Symbol)
- 公司名称 (Company Name)
- 预计上市日期 (Expected Date)
- 定价区间 (Price Range)
- 发行股数 (Shares Offered)
- 交易所 (Exchange)

# 已定价的IPO (Priced)
- 最终定价 (Final Price)
- 首日表现 (First Day Performance)
- 募集资金总额 (Deal Size)

# 已提交的IPO (Filed)
- 提交日期 (Filed Date)
- S-1文件链接
```

### 3.3 使用场景

- **IPO日历**: 提前了解即将上市的新股
- **市场热度**: 观察IPO市场的活跃程度
- **定价参考**: 了解同类公司的定价区间

### 3.4 代码位置

```
src/crawler/ipo_calendar.py  # NasdaqIPOCalendarCrawler
```

### 3.5 响应示例

```json
{
  "data": {
    "upcoming": {
      "upcomingTable": {
        "rows": [
          {
            "proposedTickerSymbol": "TMCR",
            "companyName": "Metals Royalty Co Inc.",
            "expectedPriceDate": "3/23/2026",
            "proposedSharePrice": "$18.00 - $20.00"
          }
        ]
      }
    }
  }
}
```

---

## 4. IPOScoop

### 4.1 基本信息

| 项目 | 内容 |
|------|------|
| **网站** | https://www.iposcoop.com/ipo-calendar/ |
| **数据类型** | IPO日历、评分、历史表现 |
| **更新频率** | 每日更新 |
| **身份认证** | 无需 |
| **费用** | 免费 |

### 4.2 获取的数据

```python
- IPO日历
- 公司介绍
- 行业分类
- 历史IPO表现统计
```

### 4.3 使用场景

- **备用数据源**: 当Nasdaq不可用时使用
- **历史数据**: 查看过去IPO的表现

### 4.4 代码位置

```
src/crawler/ipo_calendar.py  # IPOScoopCrawler
```

### 4.5 限制说明

- 使用HTML解析，可能因页面改版而失效
- 需要遵守robots.txt的爬虫限制

---

## 5. Benzinga (预留)

### 5.1 基本信息

| 项目 | 内容 |
|------|------|
| **网站** | https://www.benzinga.com/calendars/ipos |
| **数据类型** | IPO日历、新闻 |
| **API** | Benzinga API (需授权) |
| **费用** | 付费API |

### 5.2 状态

当前代码中预留了接口，但未完全实现。需要申请API Key才能使用。

### 5.3 代码位置

```
src/crawler/ipo_calendar.py  # 预留接口
```

---

## 6. Reddit (预留)

### 6.1 基本信息

| 项目 | 内容 |
|------|------|
| **网站** | https://www.reddit.com |
| **API** | Reddit API (PRAW) |
| **数据类型** | 社交情绪、讨论热度 |
| **费用** | 免费但有速率限制 |

### 6.2 获取的数据

```python
- 帖子标题和正文
- 评论数量和点赞数
- 情绪分析（正面/负面/中性）
- 讨论热度趋势
```

### 6.3 使用场景

- **市场情绪**: 分析散户对IPO的关注度
- **热点追踪**: 发现市场热点股票

### 6.4 状态

当前为占位符实现，需要申请Reddit API Key后完善。

### 6.5 代码位置

```
src/sentiment/analyzer.py  # 预留Reddit情绪分析
```

---

## 7. 新闻源

### 7.1 Google News RSS

```python
# 代码位置
src/crawler/news_fetcher.py

# URL
https://news.google.com/rss/search

# 用途
- 获取股票相关新闻
- 情绪分析数据源
```

### 7.2 其他新闻API (预留)

- Bloomberg API (付费)
- Reuters API (付费)
- NewsAPI (免费版有限制)

---

## 📈 数据流示意图

```
┌─────────────────────────────────────────────────────────────┐
│                        数据源层                              │
├─────────────┬─────────────┬─────────────┬─────────────────┤
│             │             │             │                 │
│  Yahoo      │   SEC       │   Nasdaq    │   IPOScoop      │
│  Finance    │   EDGAR     │   API       │   (备用)        │
│             │             │             │                 │
│ • 股价      │ • S-1招股书 │ • IPO日历   │ • IPO日历       │
│ • 基本面    │ • 13F持仓   │ • 定价信息  │ • 历史数据      │
│ • 财报日期  │ • 10-K/Q    │             │                 │
│             │             │             │                 │
└──────┬──────┴──────┬──────┴──────┬──────┴────────┬────────┘
       │             │             │               │
       └─────────────┴─────────────┴───────────────┘
                           │
                    ┌──────▼──────┐
                    │  爬虫聚合层  │
                    │  CrawlerAPI │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌────▼────┐ ┌────▼────┐
        │  数据清洗  │ │ 数据存储 │ │ 情绪分析 │
        └─────┬─────┘ └────┬────┘ └────┬────┘
              │            │           │
              └────────────┴───────────┘
                           │
                    ┌──────▼──────┐
                    │  Dashboard  │
                    │  (Streamlit)│
                    └─────────────┘
```

---

## ⚠️ 使用限制与合规

### 频率限制

| 数据源 | 限制 | 系统处理 |
|--------|------|----------|
| Yahoo Finance | 约 1-2次/秒 | 内置1秒延迟 |
| SEC EDGAR | 10次/秒 | 内置0.2秒延迟 |
| Nasdaq | 无明确限制 | 内置1秒延迟 |

### 合规要求

1. **SEC EDGAR**
   - 必须提供身份信息 (EDGAR_IDENTITY)
   - 不得用于商业用途（除非获得授权）
   - 遵守公平访问原则

2. **网站爬虫**
   - 遵守 robots.txt
   - 不得对服务器造成过大负载
   - 仅用于个人投资研究

3. **数据使用**
   - 所有数据仅供参考
   - 不构成投资建议
   - 投资有风险，入市需谨慎

---

## 🔧 扩展更多数据源

如需添加新的数据源，参考以下模板：

```python
# src/crawler/new_source.py

from .base import BaseCrawler
from .models.schemas import IPOEvent

class NewSourceCrawler(BaseCrawler):
    """新数据源爬虫"""
    
    BASE_URL = "https://api.newsource.com"
    
    def __init__(self):
        super().__init__(
            name="new_source",
            rate_limit=1.0,  # 每秒1次
        )
    
    def fetch(self) -> list[IPOEvent]:
        """获取数据"""
        response = self._request(f"{self.BASE_URL}/ipos")
        data = response.json()
        return self._parse_data(data)
```

---

**最后更新**: 2026-03-21

**版本**: v1.0.0
