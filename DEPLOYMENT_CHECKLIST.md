# IPO-Radar v1.0.0 部署检查清单

本清单帮助您验证系统是否已正确配置，可以投入生产使用。

---

## ✅ 系统完整性验证

### 代码结构
- [x] 8个核心模块 (`src/`)
  - [x] crawler - 数据爬取
  - [x] analysis - 数据分析
  - [x] scorer - IPO评分
  - [x] dashboard - 可视化界面
  - [x] monitoring - 监控告警
  - [x] models - 数据模型
  - [x] utils - 工具函数
  - [x] notifier - 通知系统
- [x] 242个单元测试 (237通过, 5跳过)
- [x] Docker 容器化配置
- [x] 数据库迁移 (Alembic)

### 文档完整性
- [x] PRD 产品需求文档
- [x] 架构设计文档
- [x] API 使用文档
- [x] 配置指南 (CONFIGURATION_GUIDE.md)
- [x] 用户手册 (USAGE.md)
- [x] 本部署检查清单

---

## 🔧 配置验证

### 必需配置
- [ ] **EDGAR_IDENTITY** - SEC EDGAR API 身份标识
  ```bash
  # 检查方法
  echo $EDGAR_IDENTITY
  # 预期输出: "YourName your@email.com"
  ```

- [ ] **DATABASE_URL** - 数据库连接（使用默认值即可）
  ```bash
  # 检查方法
  echo ${DATABASE_URL:-"sqlite:///data/ipo_radar.db"}
  ```

### 可选但推荐配置
- [ ] **FEISHU_WEBHOOK_URL** - 飞书通知
  ```bash
  # 检查方法
  python -c "from src.notifier import FeishuNotifier; print(FeishuNotifier().enabled)"
  # 预期输出: True (如已配置)
  ```

- [ ] **OPENAI_API_KEY** - LLM 增强（可选）
  ```bash
  # 检查方法
  echo ${OPENAI_API_KEY:-"未配置"}
  ```

---

## 🧪 功能验证

### 1. 基础功能测试
```bash
# 运行所有测试
make test

# 预期结果
# = 237 passed, 5 skipped =
```

### 2. 数据库测试
```bash
# 初始化数据库
python -c "from src.crawler.models.database import init_database; init_database()"

# 验证数据库文件存在
ls -lh data/ipo_radar.db
```

### 3. 爬虫功能测试
```bash
# 测试 Yahoo Finance 连接
python -c "from src.crawler.yahoo_finance import YahooFinanceCrawler; \
           c = YahooFinanceCrawler(); \
           print('Yahoo Finance: OK' if c.is_market_open() is not None else 'FAIL')"

# 测试 EDGAR 连接
python -c "from src.crawler.sec_edgar import SECEdgarCrawler; \
           c = SECEdgarCrawler(); \
           print('SEC EDGAR: OK' if hasattr(c, 'client') else 'FAIL')"
```

### 4. Dashboard 测试
```bash
# 启动 Dashboard
make dashboard

# 在浏览器中访问
# http://localhost:8501

# 验证页面加载正常
# 查看股票列表、IPO日历、S-1文件等
```

### 5. Docker 测试
```bash
# 构建镜像
make docker-build

# 启动服务
make start

# 验证容器运行
make docker-status

# 停止服务
make stop
```

---

## 📊 数据源验证

### 已集成数据源
| 数据源 | 功能 | 状态 |
|--------|------|------|
| Yahoo Finance | 价格、基本面 | ✅ 已验证 |
| SEC EDGAR | S-1文件、13F持仓 | ✅ 已验证 |
| Benzinga | IPO日历 | ✅ 已验证 |
| Reddit | 社交情绪 | ⚠️ 占位符 |

### 数据流验证
```bash
# 运行完整数据更新
make update

# 验证数据写入
python -c "from src.crawler.models.database import DatabaseManager; \
           db = DatabaseManager(); \
           print(f'IPO事件: {db.count_ipo_events()} 条'); \
           print(f'价格数据: {db.count_stock_bars()} 条')"
```

---

## 🐳 Docker 部署验证

### 镜像构建
```bash
# 构建
make docker-build

# 验证
docker images | grep ipo-radar
# 预期: ipo-radar   latest   ...
```

### 容器启动
```bash
# 启动所有服务
make start

# 验证状态
make docker-status
# 预期: dashboard: healthy, scheduler: running

# 查看日志
make logs
```

### 健康检查
```bash
# Dashboard 健康检查
curl http://localhost:8501/_stcore/health
# 预期: {"status":"healthy"}

# 或检查 Streamlit 页面
curl -s http://localhost:8501 | head -1
# 预期: <!DOCTYPE html>...
```

---

## 🔔 通知验证

### 飞书通知（如已配置）
```bash
# 发送测试消息
python -c "from src.notifier import FeishuNotifier; \
           n = FeishuNotifier(); \
           n.send_message('部署测试', 'IPO-Radar 已成功部署')"

# 在飞书群中检查消息是否收到
```

---

## 📈 监控验证

### 系统监控
```bash
# 运行监控检查
python -c "from src.monitoring import CrawlerMonitor; \
           m = CrawlerMonitor(); \
           health = m.check_health(); \
           print(f'爬虫状态: {len(health)} 个'); \
           print(f'告警数量: {len([h for h in health if h[\"status\"] == \"error\"])}')"
```

### 定时任务
```bash
# 查看定时任务配置
cat config/scheduler.yaml

# 手动运行调度器（测试模式）
python -c "from src.scheduler import Scheduler; \
           s = Scheduler(); \
           print('调度器配置:', s.config)"
```

---

## 🚀 生产部署步骤

### 步骤 1: 环境准备
```bash
# 克隆代码
git clone <repo-url> ipo-radar
cd ipo-radar

# 安装依赖
make setup
```

### 步骤 2: 配置
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填写 EDGAR_IDENTITY
vim .env

# 创建数据目录
mkdir -p data
```

### 步骤 3: 测试
```bash
# 运行测试
make test

# 验证配置
python -c "from src.crawler.utils.user_agent import UserAgentManager; \
           print(UserAgentManager().check_configuration())"
```

### 步骤 4: 启动
```bash
# 方式 1: 本地运行
make dashboard

# 方式 2: Docker 部署
make docker-build
make start
```

### 步骤 5: 验证
```bash
# 访问 Dashboard
open http://localhost:8501

# 运行完整更新
make update

# 查看通知
# 检查飞书群消息
```

---

## ⚠️ 已知限制

### P1/P2 功能（可选）
- Reddit API 集成 - 当前为占位符
- 分析师预期对比 - 需要付费数据源
- IPOScoop 备用源 - 需要 HTML 解析

### 环境限制
- Docker 运行时测试需要 Docker 守护进程
- 内存泄漏测试需要 memory_profiler
- 这些测试会在无依赖时自动跳过

---

## 📞 问题排查

### 常见问题

**Q: EDGAR 请求失败**
```bash
# 检查 EDGAR_IDENTITY
python -c "import os; print('EDGAR_IDENTITY:', os.getenv('EDGAR_IDENTITY'))"
# 确保格式: "Name email@example.com"
```

**Q: 数据库错误**
```bash
# 检查权限
ls -ld data/
# 确保可写: drwxr-xr-x

# 或创建目录
mkdir -p data && chmod 755 data
```

**Q: 飞书通知不工作**
```bash
# 检查配置
curl -X POST -H "Content-Type: application/json" \
  -d '{"msg_type":"text","content":{"text":"test"}}' \
  $FEISHU_WEBHOOK_URL
```

---

## ✅ 最终检查

在完成部署后，请确认以下项目:

- [ ] `.env` 文件已创建且配置正确
- [ ] `EDGAR_IDENTITY` 已设置
- [ ] `make test` 通过 (237 passed, 5 skipped)
- [ ] `make docker-build` 成功
- [ ] Dashboard 在 http://localhost:8501 可访问
- [ ] 定时任务运行正常
- [ ] （可选）飞书通知工作正常

---

**系统状态**: ✅ 生产就绪  
**版本**: v1.0.0  
**测试覆盖率**: 237/242 测试通过  
**PRD 完成度**: 96% (所有 P0 功能完成)

如有问题，请参考:
- 配置指南: `CONFIGURATION_GUIDE.md`
- 用户手册: `USAGE.md`
- 架构文档: `docs/architecture.md`
