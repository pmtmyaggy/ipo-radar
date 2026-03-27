# IPO-Radar 配置手册

> 详细配置指南 - 从基础到高级，全面掌握系统配置

---

## 目录

1. [配置概述](#一配置概述)
2. [核心配置项](#二核心配置项)
3. [数据源配置](#三数据源配置)
4. [通知配置](#四通知配置)
5. [数据库配置](#五数据库配置)
6. [高级配置](#六高级配置)
7. [配置示例](#七配置示例)
8. [故障排查](#八故障排查)

---

## 一、配置概述

### 1.1 配置文件位置

系统通过 `.env` 文件管理配置，位于项目根目录：

```
ipo-radar/
├── .env              # 主配置文件（不提交到Git）
├── .env.example      # 配置模板（参考）
└── ...
```

### 1.2 配置优先级

配置读取优先级（从高到低）：

1. **环境变量**: `export KEY=value`
2. **.env 文件**: 项目根目录的 `.env`
3. **默认值**: 代码中定义的默认值

### 1.3 配置分类

| 类别 | 必需 | 说明 |
|------|------|------|
| **核心配置** | ✅ 是 | 系统运行的基础配置 |
| **数据源配置** | ⚠️ 部分 | API密钥等 |
| **通知配置** | ❌ 否 | 飞书/钉钉通知 |
| **数据库配置** | ⚠️ 部分 | 数据存储配置 |
| **高级配置** | ❌ 否 | 调优参数 |

---

## 二、核心配置项

### 2.1 SEC EDGAR 身份标识

**配置项**: `EDGAR_IDENTITY`

**必需性**: ✅ **必须配置**

**用途**: 
- 访问 SEC EDGAR API
- 获取 S-1 招股书
- 获取 13F 机构持仓数据

**格式要求**:
```bash
EDGAR_IDENTITY=YourName your@email.com
```

- 必须包含姓名和邮箱
- 使用真实信息（SEC 要求）
- 邮箱需有效（可能用于联系）

**示例**:
```bash
EDGAR_IDENTITY=张三 zhangsan@example.com
EDGAR_IDENTITY=Michael pmtmyaggy@gmail.com
```

**不配置的后果**:
```
❌ 无法获取 S-1 招股书
❌ 无法获取 13F 机构持仓
❌ 基本面评分将缺失关键信息
```

**获取方式**:
- 使用您的真实姓名和邮箱
- 无需注册，直接配置即可

---

### 2.2 数据库连接

**配置项**: `DATABASE_URL`

**必需性**: ⚠️ 有默认值，可不改

**默认值**: `sqlite:///data/ipo_radar.db`

**用途**: 指定数据存储位置

**支持的数据库**:

#### SQLite (默认，推荐个人用户)

```bash
# 本地文件
DATABASE_URL=sqlite:///data/ipo_radar.db

# 绝对路径
DATABASE_URL=sqlite:////absolute/path/to/ipo_radar.db
```

**优点**:
- 无需安装，开箱即用
- 单文件存储，备份方便
- 零配置

**缺点**:
- 不适合高并发
- 大数据量时性能下降

#### PostgreSQL (推荐生产环境)

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/ipo_radar
```

**适用场景**:
- 多用户访问
- 大数据量 (>10万条记录)
- 需要远程访问

**安装 PostgreSQL**:
```bash
# macOS
brew install postgresql
brew services start postgresql

# 创建数据库
createdb ipo_radar
```

#### MySQL

```bash
DATABASE_URL=mysql://user:password@localhost:3306/ipo_radar
```

---

### 2.3 日志级别

**配置项**: `LOG_LEVEL`

**必需性**: ❌ 可选

**默认值**: `INFO`

**可选值**:
- `DEBUG`: 调试信息（开发环境）
- `INFO`: 一般信息（生产环境默认）
- `WARNING`: 警告信息
- `ERROR`: 错误信息
- `CRITICAL`: 严重错误

**配置建议**:

```bash
# 开发环境 - 查看详细日志
LOG_LEVEL=DEBUG

# 生产环境 - 只关注重要信息
LOG_LEVEL=INFO

# 静默模式 - 只显示错误
LOG_LEVEL=ERROR
```

---

## 三、数据源配置

### 3.1 Yahoo Finance

**配置方式**: 无需配置，开箱即用

**数据范围**:
- 实时股价 (15分钟延迟)
- 历史价格数据
- 基本面数据 (市值、PE等)
- 财报日期

**限制**:
- 免费版有频率限制
- 历史财报数据有限
- 部分数据可能有延迟

---

### 3.2 SEC EDGAR

**配置项**: `EDGAR_IDENTITY` (见 2.1)

**数据范围**:
- S-1 招股书
- 13F 机构持仓
- 10-K/10-Q 财报文件

**频率限制**:
- 每秒不超过 10 个请求
- 系统已内置频率控制

---

### 3.3 OpenAI / LLM 配置

用于增强情绪分析准确度。

#### 3.3.1 OpenAI 官方

```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

**获取 API Key**:
1. 访问 https://platform.openai.com/
2. 注册/登录账号
3. 创建 API Key
4. 绑定支付方式

**费用**:
- gpt-4o-mini: ~$0.001-0.003/次分析
- 月度正常使用: $1-5

#### 3.3.2 阿里云百炼 (推荐国内用户)

```bash
OPENAI_API_KEY=sk-你的百炼Key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-turbo
```

**特点**:
- 国内访问稳定
- 新用户有 100万 token 免费额度
- 中文理解能力强

**获取方式**:
1. 访问 https://dashscope.aliyun.com/
2. 用阿里云账号登录
3. 创建 API Key

#### 3.3.3 智谱 AI (免费选项)

```bash
OPENAI_API_KEY=你的智谱Key
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
OPENAI_MODEL=glm-4-flash  # 免费模型
```

**特点**:
- glm-4-flash 完全免费
- 中文优化好

#### 3.3.4 DeepSeek

```bash
OPENAI_API_KEY=sk-你的DeepSeekKey
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

**特点**:
- 推理能力强
- 价格便宜
- 新用户有 10元 免费额度

#### 3.3.5 本地 Ollama (隐私优先)

无需配置 API Key，系统会自动检测并使用本地 Ollama。

```bash
# 1. 安装 Ollama
brew install ollama

# 2. 下载模型
ollama pull llama3.2:1b

# 3. 启动服务
ollama serve
```

---

## 四、通知配置

### 4.1 飞书 Webhook

**配置项**: `FEISHU_WEBHOOK_URL`

**必需性**: ❌ 可选

**用途**: 自动推送新股提醒、持仓更新等重要信息

**格式**:
```bash
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

**获取方式**:

1. **打开飞书**，进入目标群聊
2. **点击群设置**（右上角齿轮图标）
3. **选择 "群机器人"**
4. **点击 "添加机器人"**
5. **选择 "自定义机器人"**
6. **给机器人起名字**（如"IPO-Radar"）
7. **复制 Webhook URL**
8. **将机器人添加到群聊**

**测试配置**:

```bash
python -c "
from src.notifier import FeishuNotifier
n = FeishuNotifier()
n.send_message('测试', 'IPO-Radar 配置成功！')
print('发送成功')
"
```

**通知场景**:

| 场景 | 通知内容 |
|------|---------|
| 新股申购提醒 | "明日上市: ARM Holdings (ARM), 定价区间 $47-$51" |
| 定价确定通知 | "理想汽车定价 $11.5/股，高于上限 15%" |
| 首日表现报告 | "开盘涨 35%，收盘涨 49%，成交量 5200万" |
| 机构持仓更新 | "高瓴资本新进 500万股" |
| 系统异常告警 | "数据抓取异常，请检查网络" |

---

### 4.2 钉钉 Webhook (预留)

未来版本将支持钉钉通知。

```bash
# 预留配置项
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxxxx
```

---

## 五、数据库配置

### 5.1 SQLite 优化

SQLite 默认配置已优化，一般无需修改。

**默认优化设置** (已在代码中配置):
```sql
PRAGMA journal_mode=WAL;        -- 写前日志模式
PRAGMA synchronous=NORMAL;      -- 同步模式
PRAGMA cache_size=10000;        -- 缓存大小
PRAGMA temp_store=MEMORY;       -- 临时表存储
```

**手动优化** (如需要):

```python
from src.crawler.models.database import DatabaseManager, optimize_database

db = DatabaseManager()
optimize_database(db)
```

---

### 5.2 PostgreSQL 高级配置

如果使用 PostgreSQL，可以配置连接池:

```bash
# .env
DATABASE_URL=postgresql://user:password@localhost:5432/ipo_radar

# 可选连接池配置
DB_POOL_SIZE=10          # 连接池大小
DB_MAX_OVERFLOW=20       # 最大溢出连接
DB_POOL_TIMEOUT=30       # 连接超时（秒）
```

---

### 5.3 数据库迁移

使用 Alembic 管理数据库迁移:

```bash
# 创建迁移
alembic revision --autogenerate -m "添加新表"

# 执行迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

---

## 六、高级配置

### 6.1 爬虫频率控制

**配置位置**: 各爬虫类初始化参数

**修改文件**: `src/crawler/base.py`

```python
# 默认频率限制 (秒)
DEFAULT_RATE_LIMIT = 1.0

# 各数据源频率限制
RATE_LIMITS = {
    "yahoo_finance": 0.5,    # 每 0.5 秒
    "sec_edgar": 0.2,        # 每 0.2 秒 (SEC 限制)
    "nasdaq": 1.0,           # 每 1 秒
}
```

**自定义频率**:

```python
from src.crawler.yahoo_finance import YahooFinanceCrawler

# 创建自定义频率的爬虫
crawler = YahooFinanceCrawler(rate_limit=2.0)  # 每 2 秒
```

---

### 6.2 缓存配置

**配置位置**: `src/utils/cache.py`

**默认缓存时间**:

```python
CACHE_TTL = {
    "price": 60,           # 价格缓存 60 秒
    "fundamentals": 300,   # 基本面缓存 5 分钟
    "news": 600,          # 新闻缓存 10 分钟
    "sentiment": 1800,    # 情绪分析缓存 30 分钟
}
```

**手动清除缓存**:

```python
from src.utils.cache import cache_manager
cache_manager.clear_all()
```

---

### 6.3 定时任务配置

**配置文件**: `config/scheduler.yaml`

```yaml
jobs:
  - name: "daily_scan"
    schedule: "0 9 * * *"      # 每天早上 9 点
    command: "python -m src.scorer --scan"
    
  - name: "update_prices"
    schedule: "*/15 * * * *"   # 每 15 分钟
    command: "python -m src.crawler.market_data"
    
  - name: "check_earnings"
    schedule: "0 6 * * *"      # 每天早上 6 点
    command: "python -m src.earnings.check_upcoming"
```

**Cron 表达式说明**:

```
* * * * *
│ │ │ │ │
│ │ │ │ └─ 星期 (0-7, 0和7都是周日)
│ │ │ └── 月份 (1-12)
│ │ └──── 日期 (1-31)
│ └───── 小时 (0-23)
└────── 分钟 (0-59)
```

---

### 6.4 Docker 配置

**Dockerfile 环境变量**:

```dockerfile
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
```

**docker-compose.yml 配置**:

```yaml
services:
  dashboard:
    environment:
      - ENV=production
      - DATABASE_URL=sqlite:///data/ipo_radar.db
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/app/data
      - ./.env:/app/.env:ro
```

---

## 七、配置示例

### 7.1 最小配置 (.env)

适合快速开始，使用所有默认值:

```bash
# 必需配置
EDGAR_IDENTITY=YourName your@email.com

# 其他使用默认值
```

---

### 7.2 开发环境配置 (.env)

```bash
# ============================================
# 核心配置
# ============================================
EDGAR_IDENTITY=Developer dev@example.com
DATABASE_URL=sqlite:///data/ipo_radar_dev.db
LOG_LEVEL=DEBUG

# ============================================
# 第三方API（可选）
# ============================================
# FEISHU_WEBHOOK_URL=
# OPENAI_API_KEY=

# ============================================
# 开发调优
# ============================================
# 降低缓存时间，方便调试
CACHE_TTL_PRICE=10
CACHE_TTL_NEWS=60
```

---

### 7.3 生产环境配置 (.env)

```bash
# ============================================
# 核心配置
# ============================================
EDGAR_IDENTITY=Production Team team@company.com
DATABASE_URL=postgresql://ipo_user:secure_password@db.internal:5432/ipo_radar
LOG_LEVEL=INFO

# ============================================
# 第三方API
# ============================================
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx
OPENAI_API_KEY=sk-prod-xxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o

# ============================================
# PostgreSQL 连接池
# ============================================
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_POOL_TIMEOUT=60

# ============================================
# 安全
# ============================================
# 禁用调试模式
DEBUG=false
```

---

### 7.4 国内优化配置 (.env)

适合中国大陆用户，使用国内可访问的服务:

```bash
# ============================================
# 核心配置
# ============================================
EDGAR_IDENTITY=User user@example.com
DATABASE_URL=sqlite:///data/ipo_radar.db
LOG_LEVEL=INFO

# ============================================
# 使用阿里云百炼（国内稳定）
# ============================================
OPENAI_API_KEY=sk-xxxxxxxx
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-turbo

# ============================================
# 飞书通知
# ============================================
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx

# ============================================
# 网络优化
# ============================================
# 增加超时时间（网络不稳定时）
REQUEST_TIMEOUT=60
RETRY_ATTEMPTS=5
```

---

## 八、故障排查

### 8.1 配置验证

**检查环境变量**:

```bash
# 查看已配置的环境变量
cat .env | grep -v "^#" | grep -v "^$"

# 验证配置加载
python -c "
from src.crawler.utils.user_agent import UserAgentManager
ua = UserAgentManager()
print(ua.check_configuration())
"
```

### 8.2 常见问题

#### Q1: EDGAR_IDENTITY 格式错误

**症状**: SEC 请求返回 403

**检查**:
```bash
# 必须包含空格和 @
EDGAR_IDENTITY="Name email@example.com"  # ✅ 正确
EDGAR_IDENTITY="email@example.com"        # ❌ 错误，缺少姓名
```

#### Q2: 数据库连接失败

**症状**: `sqlite3.OperationalError: unable to open database file`

**解决**:
```bash
mkdir -p data
chmod 755 data
```

#### Q3: OpenAI API 错误

**症状**: `Error: 401 Unauthorized`

**检查**:
- API Key 是否正确
- 账户是否有余额
- BASE_URL 是否正确（某些平台需要 `/v1` 结尾）

#### Q4: 飞书通知失败

**症状**: 消息未收到

**排查**:
```bash
# 测试 Webhook
curl -X POST -H "Content-Type: application/json" \
  -d '{"msg_type":"text","content":{"text":"test"}}' \
  $FEISHU_WEBHOOK_URL
```

### 8.3 配置热重载

修改 `.env` 后，需要重启服务生效:

```bash
# 停止服务
pkill -f streamlit

# 重新启动
make dashboard
```

---

## 附录

### A. 环境变量完整列表

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `EDGAR_IDENTITY` | ✅ | - | SEC EDGAR 身份标识 |
| `DATABASE_URL` | ❌ | SQLite | 数据库连接字符串 |
| `LOG_LEVEL` | ❌ | INFO | 日志级别 |
| `FEISHU_WEBHOOK_URL` | ❌ | - | 飞书 Webhook |
| `OPENAI_API_KEY` | ❌ | - | OpenAI API Key |
| `OPENAI_BASE_URL` | ❌ | OpenAI官方 | API 基础 URL |
| `OPENAI_MODEL` | ❌ | gpt-4o-mini | 模型名称 |
| `DB_POOL_SIZE` | ❌ | 5 | 连接池大小 |
| `DB_MAX_OVERFLOW` | ❌ | 10 | 最大溢出连接 |
| `DB_POOL_TIMEOUT` | ❌ | 30 | 连接超时 |
| `PYTHONPATH` | ❌ | - | Python 路径 |

### B. 配置文件模板

```bash
# 复制模板
cp .env.example .env

# 编辑配置
vim .env

# 验证配置
make test
```

### C. 安全建议

1. **不要提交 `.env` 到 Git**
   ```bash
   # .gitignore
   .env
   *.key
   *.pem
   ```

2. **定期轮换 API Key**
   - 每 3-6 个月更换一次
   - 使用环境变量而非硬编码

3. **限制数据库访问权限**
   ```sql
   -- PostgreSQL
   CREATE USER ipo_user WITH PASSWORD 'strong_password';
   GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO ipo_user;
   ```

---

**最后更新**: 2026-03-21

**版本**: v1.0.0
