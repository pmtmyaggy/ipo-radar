# IPO-Radar 全量运行配置指南

> 按此清单配置，可让系统 100% 功能正常运行

---

## 一、必需配置（无此系统无法运行）

### 1. SEC EDGAR 身份标识 ⭐⭐⭐ 最重要

**用途**: 爬取 S-1 招股书、13F 机构持仓数据

**为什么必需**: SEC 要求所有访问 EDGAR API 的用户必须提供身份信息

**配置方法**:
```bash
# 编辑 .env 文件
vim /Users/zhiyuchen/Downloads/美股爬虫/ipo-radar/.env
```

**填写内容**:
```bash
# 格式: "你的真实姓名 你的真实邮箱@example.com"
EDGAR_IDENTITY=张三 zhangsan@gmail.com
```

**验证方式**:
```bash
cd /Users/zhiyuchen/Downloads/美股爬虫/ipo-radar
python -c "from src.crawler.sec_edgar import SECEdgarCrawler; c = SECEdgarCrawler(); print('✅ EDGAR 配置成功' if c.client else '❌ 失败')"
```

**不配置的后果**:
- ❌ 无法获取 S-1 招股书
- ❌ 无法获取 13F 机构持仓数据
- ❌ 基本面评分将缺失关键信息

---

### 2. 数据目录权限

**用途**: 存储 SQLite 数据库和日志文件

**配置方法**:
```bash
# 创建目录并设置权限
mkdir -p /Users/zhiyuchen/Downloads/美股爬虫/ipo-radar/data
mkdir -p /Users/zhiyuchen/Downloads/美股爬虫/ipo-radar/logs
chmod 755 /Users/zhiyuchen/Downloads/美股爬虫/ipo-radar/data
chmod 755 /Users/zhiyuchen/Downloads/美股爬虫/ipo-radar/logs
```

**验证方式**:
```bash
ls -ld /Users/zhiyuchen/Downloads/美股爬虫/ipo-radar/data
# 应该显示: drwxr-xr-x
```

---

### 3. Python 路径配置（已自动修复）

**状态**: ✅ 已内置修复，无需手动配置

**系统已自动处理**:
- `src/dashboard/app.py` 已添加正确的 `sys.path`
- Makefile 已设置 `PYTHONPATH`

---

## 二、强烈建议配置（影响核心功能体验）

### 4. 飞书 Webhook 通知 ⭐⭐⭐

**用途**: 接收新股提醒、定价通知、持仓更新等重要信息

**为什么强烈建议**: 无通知时只能主动打开 Dashboard 查看，容易错过时机

**获取方式**:
1. 打开飞书，进入目标群聊
2. 点击群设置 → 群机器人 → 添加机器人 → 自定义机器人
3. 复制 Webhook URL（格式: `https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx`）

**配置方法**:
```bash
# 编辑 .env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxxxxx
```

**验证方式**:
```bash
python -c "from src.notifier import FeishuNotifier; n = FeishuNotifier(); n.send_message('测试', 'IPO-Radar 通知配置成功')"
```

**查看效果**: 飞书群中会收到测试消息

---

### 5. OpenAI API Key ⭐⭐

**用途**: LLM 增强的情绪分析（更准确的新闻/社交媒体情绪判断）

**为什么建议**: 不使用时会 fallback 到关键词分析，准确度下降但仍可用

**获取方式**:
1. 访问 https://platform.openai.com/
2. 注册/登录账号
3. 创建 API Key

**配置方法**:
```bash
# 编辑 .env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

**验证方式**:
```bash
python -c "from src.sentiment.analyzer import SentimentAnalyzer; a = SentimentAnalyzer(); print('✅ OpenAI 可用' if a.openai_client else '⚠️ 使用关键词分析')"
```

**注意事项**:
- 使用 OpenAI API 会产生费用
- 系统有内置的关键词分析作为备选

---

## 三、可选配置（进阶功能）

### 6. 数据库配置

**默认配置**（一般无需修改）:
```bash
DATABASE_URL=sqlite:///data/ipo_radar.db
```

**生产环境建议使用 PostgreSQL**:
```bash
# 编辑 .env
DATABASE_URL=postgresql://username:password@localhost:5432/ipo_radar
```

**配置后需执行**:
```bash
# 初始化数据库表
python -c "from src.crawler.models.database import init_database; init_database()"

# 运行迁移
alembic upgrade head
```

---

### 7. 日志级别配置

**开发环境**（调试信息更详细）:
```bash
LOG_LEVEL=DEBUG
```

**生产环境**（只显示重要信息）:
```bash
LOG_LEVEL=INFO
```

---

### 8. 定时任务配置

**用途**: 自动运行数据更新

**配置文件**: `/Users/zhiyuchen/Downloads/美股爬虫/ipo-radar/config/scheduler.yaml`

**默认任务**:
```yaml
jobs:
  - name: "daily_scan"
    schedule: "0 9 * * *"  # 每天早上9点运行
    command: "python -m src.scorer.daily_scan"

  - name: "update_prices"
    schedule: "*/15 * * * *"  # 每15分钟更新价格
    command: "python -m src.crawler.market_data"
```

**手动运行测试**:
```bash
# 运行一次完整更新
make update
```

---

## 四、配置后验证清单

### 第一步: 配置验证
```bash
cd /Users/zhiyuchen/Downloads/美股爬虫/ipo-radar

# 1. 检查 EDGAR 配置
echo "EDGAR_IDENTITY: $EDGAR_IDENTITY"

# 2. 检查飞书配置
echo "FEISHU_WEBHOOK_URL: ${FEISHU_WEBHOOK_URL:-未配置}"

# 3. 检查 OpenAI 配置
echo "OPENAI_API_KEY: ${OPENAI_API_KEY:+已配置}"
```

### 第二步: 功能测试
```bash
# 1. 运行所有测试
make test
# 期望: 237 passed, 5 skipped

# 2. 测试 EDGAR 连接
python -c "
from src.crawler.sec_edgar import SECEdgarCrawler
crawler = SECEdgarCrawler()
filings = crawler.get_recent_s1_filings(days=1)
print(f'✅ EDGAR 正常，获取到 {len(filings)} 条 S-1 记录')
"

# 3. 测试 Yahoo Finance
python -c "
from src.crawler.yahoo_finance import YahooFinanceCrawler
crawler = YahooFinanceCrawler()
bars = crawler.get_stock_bars('AAPL')
print(f'✅ Yahoo Finance 正常，获取到 {len(bars)} 条价格数据')
"

# 4. 测试飞书通知（如已配置）
python -c "
from src.notifier import FeishuNotifier
n = FeishuNotifier()
if n.enabled:
    n.send_message('系统测试', '所有配置正常，系统已就绪')
    print('✅ 飞书通知已发送')
else:
    print('⚠️ 飞书未配置')
"
```

### 第三步: Dashboard 验证
```bash
# 启动 Dashboard
make dashboard

# 在浏览器中验证:
# 1. 打开 http://localhost:8501
# 2. 检查左侧导航栏所有菜单可正常点击
# 3. 检查股票列表页面有数据显示
# 4. 检查 IPO 日历页面有数据
```

---

## 五、配置优先级总结

| 优先级 | 配置项 | 不配置的后果 | 配置难度 |
|--------|--------|-------------|----------|
| 🔴 P0 | EDGAR_IDENTITY | 无法获取 S-1 和 13F 数据 | ⭐ 简单 |
| 🔴 P0 | 数据目录权限 | 数据库无法写入 | ⭐ 简单 |
| 🟡 P1 | FEISHU_WEBHOOK_URL | 无自动通知 | ⭐⭐ 需飞书操作 |
| 🟡 P1 | OPENAI_API_KEY | 情绪分析准确度下降 | ⭐⭐ 需注册 OpenAI |
| 🟢 P2 | PostgreSQL | 大数据量时性能下降 | ⭐⭐⭐ 需安装 PG |
| 🟢 P2 | 定时任务 | 需手动运行更新 | ⭐⭐ 编辑 YAML |

---

## 六、一键配置脚本

保存为 `setup.sh`，运行 `bash setup.sh`:

```bash
#!/bin/bash

PROJECT_DIR="/Users/zhiyuchen/Downloads/美股爬虫/ipo-radar"
cd $PROJECT_DIR

echo "=== IPO-Radar 配置向导 ==="
echo ""

# 1. 创建目录
echo "[1/4] 创建数据目录..."
mkdir -p data logs
chmod 755 data logs
echo "✅ 目录创建完成"

# 2. 检查 .env
echo ""
echo "[2/4] 检查环境变量配置..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️ 已创建 .env 文件，请编辑填写 EDGAR_IDENTITY"
else
    echo "✅ .env 文件已存在"
fi

# 3. 检查 EDGAR_IDENTITY
echo ""
echo "[3/4] 验证 EDGAR 配置..."
source .env
if [[ "$EDGAR_IDENTITY" == "YourName your@email.com" ]] || [[ -z "$EDGAR_IDENTITY" ]]; then
    echo "❌ EDGAR_IDENTITY 未配置或仍为默认值"
    echo "   请编辑 .env 文件: EDGAR_IDENTITY=你的名字 你的邮箱@example.com"
    exit 1
else
    echo "✅ EDGAR_IDENTITY: $EDGAR_IDENTITY"
fi

# 4. 安装依赖
echo ""
echo "[4/4] 安装 Python 依赖..."
pip install -q -r requirements.txt
echo "✅ 依赖安装完成"

# 5. 初始化数据库
echo ""
echo "初始化数据库..."
python -c "from src.crawler.models.database import init_database; init_database()"
echo "✅ 数据库初始化完成"

# 6. 运行测试
echo ""
echo "运行测试..."
python -m pytest tests/ -q --tb=no
echo "✅ 测试完成"

echo ""
echo "=== 配置完成 ==="
echo ""
echo "启动命令:"
echo "  make dashboard    # 启动可视化界面"
echo "  make update       # 手动运行数据更新"
echo "  make test         # 运行测试"
echo ""
echo "访问地址: http://localhost:8501"
```

---

## 七、常见问题

### Q1: 配置了 EDGAR_IDENTITY 但仍然获取不到数据？

**检查**:
```bash
# 确认环境变量已加载
source .env
echo $EDGAR_IDENTITY

# 确认格式正确（必须包含 @）
# 正确: "张三 zhangsan@gmail.com"
# 错误: "zhangsan@gmail.com" (缺少姓名)
```

### Q2: 飞书通知没有收到？

**检查**:
1. Webhook URL 是否完整（以 `https://` 开头）
2. 机器人是否被添加到群聊
3. 群聊设置中是否启用了该机器人

### Q3: 某些测试失败？

**正常情况**:
- 5 个测试会被跳过（Docker 相关、内存分析相关）
- 只要核心测试（237个）通过即可

---

## 八、配置完成后的完整功能清单

配置完成后，你将拥有：

- ✅ **实时股价数据** - Yahoo Finance 每 15 分钟更新
- ✅ **IPO 日历** - 自动抓取未来上市新股
- ✅ **S-1 招股书** - SEC EDGAR 官方文件
- ✅ **13F 机构持仓** - 季度机构持仓变化
- ✅ **智能评分** - 5 维度量化评分
- ✅ **飞书通知** - 重要事件自动推送
- ✅ **情绪分析** - LLM 增强的新闻情绪判断
- ✅ **可视化 Dashboard** - 一站式数据看板

---

**下一步**: 完成上述配置后，运行 `make dashboard` 开始使用！
