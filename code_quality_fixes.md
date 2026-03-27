# 代码质量修复报告

## 已修复问题

### 🔴 严重问题

#### 1. Import 顺序错误 (base.py)
**问题**: `datetime` 在第326行使用，但直到第361行才导入
**修复**: 将 `from datetime import datetime` 移到文件顶部（第10行）
**文件**: `src/crawler/base.py`

```python
# 修复前 - 第361行
from datetime import datetime  # Import too late!

# 修复后 - 第10行
from datetime import datetime
```

#### 2. 数据库连接泄漏 (api.py)
**问题**: 多个 `sqlite3.connect()` 直接调用绕过 db_manager，可能导致连接泄漏
**文件**: `src/crawler/api.py`

**修复内容**:
- `refresh_ipo_calendar()` (第100-146行): 使用 SQLAlchemy ORM + UPSERT 替代原始 SQL
- `get_lockup_info()` (第385-450行): 使用 `db_manager.session_scope()` 和 ORM 模型

```python
# 修复前 - 直接使用 sqlite3
conn = sqlite3.connect('data/ipo_radar.db')
cursor = conn.cursor()
# ... 操作 ...
conn.close()  # 可能不执行

# 修复后 - 使用 db_manager
with self.db_manager.session_scope() as session:
    record = session.query(LockupInfoModel).filter(...).first()
    # 自动提交/回滚和关闭
```

### 🟡 中等问题

#### 3. 线程安全问题 (edgar_monitor.py)
**问题**: `self._running` 标志在多线程环境中没有锁保护
**文件**: `src/crawler/edgar_monitor.py`

**修复**:
- 添加 `import threading`
- 在 `__init__` 中创建 `self._running_lock = threading.Lock()`
- 使用锁保护 `_running` 的读写操作

```python
with self._running_lock:
    self._running = True

while True:
    with self._running_lock:
        if not self._running:
            break
```

#### 4. 硬编码默认值 (user_agent.py)
**问题**: 默认联系邮箱硬编码为 `"contact@ipo-radar.com"`
**文件**: `src/crawler/utils/user_agent.py`

**修复**: 添加环境变量支持，并在未配置时抛出明确错误

```python
env_email = os.getenv("CONTACT_EMAIL", "")
if env_email and "@" in env_email:
    self.contact_email = env_email
elif contact_email and "@" in contact_email:
    self.contact_email = contact_email
else:
    raise ValueError(
        "Contact email is required. Set CONTACT_EMAIL environment variable "
        "or pass contact_email parameter."
    )
```

## 已修复的未实现功能

### ✅ IPOScoop 解析器
**文件**: `src/crawler/ipo_calendar.py`

**实现内容**:
- 完整的 HTML 表格解析逻辑 (`_parse_calendar`)
- 支持解析表格中的公司名、股票代码、承销商、股数、价格区间、交易规模、预期日期
- 日期解析支持多种格式（如 "3/27/2026 Friday"）
- 自动清理股票代码（去掉 .U, .WS 等后缀）
- 交易规模解析（支持 mil/bil 格式）

**使用方法**:
```python
from src.crawler.ipo_calendar import IPOScoopCrawler
crawler = IPOScoopCrawler()
events = crawler.fetch()  # 返回 list[IPOEvent]
```

### ✅ Reddit 爬虫
**文件**: `src/crawler/news_fetcher.py`

**实现内容**:
- 使用 Reddit JSON API（无需认证密钥）
- 支持多子版块监控（r/stocks, r/wallstreetbets, r/investing, r/IPOs）
- 智能股票代码提取（支持 $SYMBOL 格式）
- 自动过滤旧帖子（基于天数参数）
- 基于点赞数计算相关性分数

**使用方法**:
```python
from src.crawler.news_fetcher import RedditCrawler
reddit = RedditCrawler()
posts = reddit.fetch(ticker="AAPL", days=7, limit=25)
```

### 🟡 宽泛的异常处理
- 代码中有多个 `except Exception` 块（约81处）
- 修复这些需要仔细分析每个地方可能出现的具体异常类型
- 建议：逐步重构关键路径的异常处理

### 🟢 未使用的 AdaptiveRateLimiter
- 该类在测试中使用，为未来扩展保留
- 不建议删除，因为有测试覆盖

## 验证

所有修复已通过语法检查:
```bash
python -m py_compile src/crawler/base.py
python -m py_compile src/crawler/api.py
python -m py_compile src/crawler/edgar_monitor.py
python -m py_compile src/crawler/utils/user_agent.py
python -c "from src.crawler.base import BaseCrawler; from src.crawler.api import CrawlerAPI"
```

## 建议后续工作

1. **异常处理细化**: 为核心爬虫路径添加具体异常类型
2. **单元测试**: 为修复的代码添加测试用例
3. **类型检查**: 引入 mypy 进行静态类型检查
4. **代码审查**: 建立代码审查流程防止类似问题
