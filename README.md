# IPO-Radar - IPO决策信息系统

📡 一个综合性的美股新股(IPO)二级市场决策信息系统，帮助投资者系统性地识别和评估新上市股票的交易机会。

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 核心功能

IPO-Radar 识别和跟踪四个关键交易窗口：

| 窗口 | 说明 | 关键指标 |
|------|------|----------|
| 🚀 **首日回调** | IPO首日破发后的反弹机会 | 回调幅度、成交量 |
| 📐 **底部突破** | IPO后形成底部形态并突破 | 形态质量、RS强度、成交量确认 |
| 🔒 **禁售期到期** | 锁定股份解禁前后的波动 | 供应冲击占比、持有人类型 |
| 📊 **首次财报** | IPO后第一份财报的博弈 | EPS/Revenue Surprise、Guidance |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Streamlit Dashboard                     │
│  [新股监控] [基本面] [形态识别] [禁售期] [情绪] [业绩] [评分]  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      Signal Aggregator                       │
│                   综合评分引擎 + 信号聚合                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │
│  │ Radar  │ │Screener│ │ Pattern│ │ Lockup │ │Sentiment│    │
│  │(监控)  │ │(筛选)  │ │(形态)  │ │(禁售期)│ │ (情绪)  │    │
│  └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘    │
│       └──────────┴──────────┴────┬─────┴──────────┘         │
│                                  ↓                          │
│  ┌───────────────────────────────────────────────────────┐ │
│  │                  Crawler System                        │ │
│  │  [IPO日历] [S-1解析] [行情] [新闻] [财报] [EDGAR监控]    │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    SQLite / PostgreSQL
```

---

## 📦 安装

### 环境要求

- Python 3.11+
- Poetry (推荐) 或 pip
- (可选) Ollama - 用于本地LLM情绪分析

### 使用 Poetry 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/ipo-radar.git
cd ipo-radar

# 安装依赖
poetry install

# 激活环境
poetry shell
```

### 使用 pip 安装

```bash
pip install -r requirements.txt
```

---

## ⚙️ 配置

### 1. 环境变量

复制示例配置文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入必要的配置：

```bash
# 必填：联系邮箱（用于SEC EDGAR访问）
EDGAR_USER_AGENT="IPO-Radar your-email@example.com"

# 可选：数据库配置（默认SQLite）
DATABASE_URL=sqlite:///data/ipo_radar.db

# 可选：飞书Webhook（用于通知）
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx

# 可选：Reddit API（用于社交情绪）
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
```

### 2. 初始化数据库

```bash
python -c "from src.crawler.models.database import init_database; init_database()"
```

---

## 🚀 快速开始

### 启动仪表盘

```bash
# 使用 Make
make dashboard

# 或直接运行
streamlit run src/dashboard/app.py
```

仪表盘将在 `http://localhost:8501` 启动。

### 运行每日扫描

```bash
# 扫描观察名单
make scan

# 或
python -m src.scorer --scan
```

### 分析单个股票

```bash
python -m src.scorer --ticker CAVA
```

---

## 🛠️ 开发指南

### 项目结构

```
ipo-radar/
├── src/                          # 源代码
│   ├── crawler/                  # 爬虫系统
│   │   ├── models/              # 数据模型
│   │   ├── utils/               # 工具函数
│   │   ├── base.py              # 爬虫基类
│   │   └── ...                  # 各爬虫实现
│   ├── radar/                    # 新股监控
│   ├── screener/                 # 基本面筛选
│   ├── pattern/                  # 形态识别
│   ├── lockup/                   # 禁售期跟踪
│   ├── sentiment/                # 情绪分析
│   ├── earnings/                 # 业绩追踪
│   ├── scorer/                   # 综合评分
│   └── dashboard/                # 仪表盘
├── tests/                        # 测试
├── data/                         # 数据存储
├── .spec/                        # Spec Kit 规范
└── docs/                         # 文档
```

### 运行测试

```bash
# 运行所有测试
make test

# 或
pytest

# 带覆盖率报告
pytest --cov=src --cov-report=html
```

### 代码风格

```bash
# 格式化代码
make format

# 或
black src/
ruff check src/

# 类型检查
mypy src/
```

---

## 📊 数据源

| 数据类型 | 主要源 | 备用源 | 费用 |
|----------|--------|--------|------|
| IPO日历 | Nasdaq API | IPOScoop | 免费 |
| S-1招股书 | SEC EDGAR | sec-api.io | 免费/$50+ |
| 行情数据 | Yahoo Finance | Polygon.io | 免费/$29+ |
| 新闻 | Google News RSS | Benzinga | 免费/$79+ |
| 社交情绪 | Reddit API | StockTwits | 免费 |

---

## 🔒 合规与限制

- **SEC EDGAR**: 最多10次/秒，建议5次/秒，User-Agent必须包含邮箱
- **Reddit API**: 60次/分钟，需OAuth认证
- **Nasdaq**: 无明确限制，建议1次/秒

---

## 📖 文档

- [产品宪法](.spec/constitution.md) - 产品愿景与核心规则
- [技术设计](.spec/design.md) - 架构设计与数据流
- [任务清单](.spec/tasks.md) - 开发任务追踪
- [API文档](docs/api.md) - 模块接口文档（待补充）

---

## 🤝 贡献

欢迎贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何参与。

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件。

---

## ⚠️ 免责声明

本系统仅供学习和研究使用，不构成投资建议。投资有风险，入市需谨慎。

---

## 🔗 相关链接

- [SEC EDGAR](https://www.sec.gov/edgar)
- [Nasdaq IPO Calendar](https://www.nasdaq.com/market-activity/ipos)
- [OpenSpec](https://github.com/Fission-AI/OpenSpec) - Spec-Driven开发方法

---

Made with ❤️ by IPO-Radar Team
