# IPO-Radar 配置指南

本文档列出项目中所有需要配置的项，帮助您正确设置和部署系统。

---

## 📋 配置清单总览

| 类别 | 必需 | 可选 | 说明 |
|------|------|------|------|
| 核心配置 | ✅ 4项 | - | 系统运行的基础配置 |
| 第三方API | - | 3项 | 增强功能的外部服务 |
| 数据库 | ✅ 1项 | 3项 | 数据存储配置 |
| Docker | - | 2项 | 容器化部署配置 |
| 监控告警 | - | 2项 | 监控和通知配置 |

---

## 一、核心配置（必需）

### 1. SEC EDGAR 身份标识 ⭐ **最重要**

**配置项**: `EDGAR_IDENTITY`  
**用途**: 访问 SEC EDGAR API  
**格式**: `YourName your@email.com`

**设置方法**:
```bash
# .env 文件
EDGAR_IDENTITY=YourName your@email.com

# 或环境变量
export EDGAR_IDENTITY="YourName your@email.com"
```

**获取方式**:
- 使用您的真实姓名和邮箱
- SEC 要求所有访问者提供身份信息
- 示例: `John Doe john.doe@example.com`

**验证命令**:
```bash
python -c "from src.crawler.utils.user_agent import UserAgentManager; \
           ua = UserAgentManager(); \
           print(ua.check_configuration())"
```

---

### 2. 数据库连接

**配置项**: `DATABASE_URL`  
**默认值**: `sqlite:///data/ipo_radar.db`  
**用途**: 数据存储位置

**选项**:
```bash
# SQLite (默认，推荐本地使用)
DATABASE_URL=sqlite:///data/ipo_radar.db

# PostgreSQL (生产环境)
DATABASE_URL=postgresql://user:password@localhost:5432/ipo_radar

# MySQL
DATABASE_URL=mysql://user:password@localhost:3306/ipo_radar
```

**高级配置** (可选):
```bash
# 连接池配置
DB_POOL_SIZE=10          # 连接池大小
DB_MAX_OVERFLOW=20       # 最大溢出连接
DB_POOL_TIMEOUT=30       # 连接超时（秒）
```

---

### 3. 日志级别

**配置项**: `LOG_LEVEL`  
**默认值**: `INFO`  
**选项**: `DEBUG`, `INFO`, `WARNING`, `ERROR`

```bash
# 开发环境
LOG_LEVEL=DEBUG

# 生产环境
LOG_LEVEL=INFO
```

---

### 4. 项目路径

**配置项**: `PYTHONPATH`  
**用途**: Python 模块搜索路径

**设置方法**:
```bash
# .env 或启动时
export PYTHONPATH=/path/to/ipo-radar/src
```

---

## 二、第三方API配置（可选）

### 5. 飞书 Webhook 通知

**配置项**: `FEISHU_WEBHOOK_URL`  
**用途**: 发送监控告警和扫描报告到飞书  
**必需性**: 可选，但推荐配置

**获取方式**:
1. 在飞书群聊中添加 "自定义机器人"
2. 复制 Webhook URL

**设置方法**:
```bash
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxx
```

**测试命令**:
```bash
python -c "from src.notifier import FeishuNotifier; \
           n = FeishuNotifier(); \
           n.send_message('Test', 'Configuration successful')"
```

---

### 6. OpenAI API（情绪分析增强）

**配置项**: `OPENAI_API_KEY`  
**用途**: LLM 情绪分析  
**必需性**: 可选，使用关键词分析作为 fallback

**获取方式**:
- 访问 https://platform.openai.com/
- 创建 API Key

**设置方法**:
```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

**注意**: 
- 使用 OpenAI API 会产生费用
- 系统会使用本地关键词分析作为备选

---

### 7. Reddit API（社交数据）

**配置项**: 预留接口，当前未完整实现  
**用途**: 获取 Reddit 讨论数据  
**必需性**: 可选

**未来配置**:
```bash
REDDIT_CLIENT_ID=xxx
REDDIT_CLIENT_SECRET=xxx
REDDIT_USER_AGENT=IPO-Radar/0.1.0
```

---

## 三、数据库配置（可选调优）

### 8. SQLite 优化

**配置项**: SQLite PRAGMA 设置  
**位置**: `src/crawler/models/database.py`

**默认优化** (已内置):
```sql
PRAGMA journal_mode=WAL;        -- 写前日志模式
PRAGMA synchronous=NORMAL;      -- 同步模式
PRAGMA cache_size=10000;        -- 缓存大小
PRAGMA temp_store=MEMORY;       -- 临时表存储
```

**手动优化**:
```python
from src.crawler.models.database import DatabaseManager, optimize_database

db = DatabaseManager()
optimize_database(db)
```

---

### 9. 数据库索引

**配置项**: `src/crawler/models/indexes.py`  
**用途**: 查询性能优化  
**状态**: 已内置，自动创建

**手动创建**:
```python
from src.crawler.models.database import DatabaseManager
from src.crawler.models.indexes import create_indexes

db = DatabaseManager()
create_indexes(db)
```

---

## 四、Docker 配置（可选）

### 10. Docker 环境变量

**配置文件**: `docker-compose.yml`

**关键配置项**:
```yaml
environment:
  - ENV=production          # 环境: production/development
  - DATABASE_URL=sqlite:///data/ipo_radar.db
  - LOG_LEVEL=INFO
```

**端口映射**:
```yaml
ports:
  - "8501:8501"             # Streamlit 仪表盘
```

**卷挂载**:
```yaml
volumes:
  - ./data:/app/data        # 数据持久化
  - ./.env:/app/.env:ro     # 环境变量（只读）
```

---

### 11. Dockerfile 配置

**位置**: `Dockerfile`

**可自定义项**:
```dockerfile
FROM python:3.11-slim       # Python 版本
EXPOSE 8501                 # 暴露端口
```

---

## 五、监控告警配置（可选）

### 12. 监控告警

**配置项**: `src/monitoring/alerter.py`  
**用途**: 系统健康监控和告警

**环境变量**:
```bash
# 飞书告警（与通知共用）
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxx
```

**监控指标** (自动收集):
- 爬虫成功率
- 响应时间
- 最后成功运行时间
- 数据库表状态

**告警规则**:
- 爬虫超过 2 小时未成功运行 → 发送告警
- 数据表超过 2 小时未更新 → 发送告警

---

### 13. 缓存配置

**配置项**: `src/utils/cache.py`  
**用途**: 数据缓存，减少重复请求

**TTL 设置** (已内置):
```python
价格缓存: 60秒
基本面缓存: 300秒 (5分钟)
新闻缓存: 600秒 (10分钟)
```

**手动清除**:
```python
from src.utils.cache import cache_manager
cache_manager.clear_all()
```

---

## 六、配置检查清单

### 部署前检查

- [ ] 创建 `.env` 文件
- [ ] 配置 `EDGAR_IDENTITY`
- [ ] 配置 `DATABASE_URL`（如不使用默认SQLite）
- [ ] 配置 `FEISHU_WEBHOOK_URL`（如需通知）
- [ ] 配置 `OPENAI_API_KEY`（如需LLM增强）
- [ ] 创建 `data/` 目录
- [ ] 验证配置

### 验证命令

```bash
# 1. 检查环境变量
cat .env

# 2. 验证 EDGAR 配置
python -c "from src.crawler.utils.user_agent import UserAgentManager; \
           import os; \
           print('EDGAR_IDENTITY:', os.getenv('EDGAR_IDENTITY')); \
           ua = UserAgentManager(); \
           print('配置有效:', ua.check_configuration())"

# 3. 测试数据库连接
python -c "from src.crawler.models.database import DatabaseManager, init_database; \
           init_database(); \
           print('数据库初始化成功')"

# 4. 测试飞书通知（如配置）
python -c "from src.notifier import FeishuNotifier; \
           n = FeishuNotifier(); \
           print('飞书通知已启用:', n.enabled)"

# 5. 运行测试
make test
```

---

## 七、配置文件模板

### 最小配置 `.env`

```bash
# 必需
EDGAR_IDENTITY=YourName your@email.com

# 可选（使用默认值）
# DATABASE_URL=sqlite:///data/ipo_radar.db
# LOG_LEVEL=INFO
```

### 完整配置 `.env`

```bash
# ============================================
# 核心配置（必需）
# ============================================
EDGAR_IDENTITY=YourName your@email.com
DATABASE_URL=sqlite:///data/ipo_radar.db
LOG_LEVEL=INFO

# ============================================
# 第三方API（可选）
# ============================================
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# ============================================
# 数据库优化（可选）
# ============================================
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30

# ============================================
# 高级配置（通常不需要修改）
# ============================================
# PYTHONPATH=/path/to/ipo-radar/src
```

---

## 八、常见问题

### Q1: EDGAR_IDENTITY 格式错误

**错误**:
```
SEC EDGAR request failed: 403 Forbidden
```

**解决**:
- 确保格式: `YourName your@email.com`
- 使用真实邮箱
- 检查环境变量是否正确加载

### Q2: 数据库权限错误

**错误**:
```
sqlite3.OperationalError: unable to open database file
```

**解决**:
```bash
# 创建数据目录
mkdir -p data
chmod 755 data

# 或使用绝对路径
DATABASE_URL=sqlite:////absolute/path/to/ipo-radar/data/ipo_radar.db
```

### Q3: 飞书通知不工作

**检查**:
```bash
# 验证 Webhook URL
curl -X POST -H "Content-Type: application/json" \
  -d '{"msg_type":"text","content":{"text":"test"}}' \
  $FEISHU_WEBHOOK_URL
```

---

## 九、环境特定配置

### 开发环境

```bash
LOG_LEVEL=DEBUG
DATABASE_URL=sqlite:///data/ipo_radar_dev.db
```

### 生产环境

```bash
LOG_LEVEL=INFO
DATABASE_URL=postgresql://user:pass@localhost/ipo_radar
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxx
```

### Docker 环境

```bash
# 已在 docker-compose.yml 中配置
# 只需确保 .env 文件存在
```

---

**配置文档版本**: 1.0  
**最后更新**: 2026-03-21
