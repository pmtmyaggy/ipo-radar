# IPO-Radar 开发任务计划

> **Project**: IPO-Radar  
> **Start Date**: 2026-03-19  
> **Estimated Duration**: 21 工作日

---

## Phase 1: 基础架构 (Day 1-2)

### 1.1 项目初始化 ✅ COMPLETED
- [x] Spec Kit 规范体系建立
- [x] Planning with Files 配置
- [x] 产品宪法 (Constitution) 编写
- [x] pyproject.toml 配置
- [x] .env.example 配置
- [x] 数据库模型定义 (SQLAlchemy)
- [x] 基础目录结构创建

### 1.2 爬虫基础组件 ✅ COMPLETED
- [x] BaseCrawler 抽象基类
- [x] RateLimiter 频率限制器
- [x] Retry 装饰器
- [x] User-Agent 管理
- [x] 数据库连接管理

---

## Phase 2: 爬虫层开发 (Day 3-8) ✅ COMPLETED

### 2.1 IPO日历爬虫
- [ ] Nasdaq API 集成
- [ ] SEC EDGAR EFTS 监控
- [ ] IPOScoop 备用源
- [ ] IPOEvent 数据模型
- [ ] 定时任务配置

### 2.2 S-1解析器
- [ ] S-1文件下载
- [ ] HTML解析提取
- [ ] 财务指标提取
- [ ] 禁售期条款解析
- [ ] XBRL解析（可选）

### 2.3 行情数据爬虫
- [ ] yfinance集成
- [ ] 日线数据获取
- [ ] 历史数据回填
- [ ] 盘中快照

### 2.4 新闻爬虫
- [ ] Google News RSS
- [ ] Reddit API
- [ ] 新闻情绪预标记

### 2.5 财报数据爬虫
- [ ] 财报日期获取
- [ ] 财报数据解析
- [ ] 分析师预期对比

### 2.6 禁售期爬虫
- [ ] 从S-1提取禁售期信息
- [ ] 到期日计算
- [ ] 供应冲击计算

### 2.7 SEC实时监控
- [ ] EDGAR EFTS轮询
- [ ] 新文件检测
- [ ] 触发器配置

---

## Phase 3: 分析模块开发 (Day 9-14) ✅ COMPLETED

### 3.1 新股监控 (radar)
- [ ] IPOStatus 数据模型
- [ ] 观察名单管理
- [ ] 自动发现新IPO
- [ ] 状态更新协调

### 3.2 基本面筛选 (screener)
- [ ] S1Metrics 提取
- [ ] QuickScore 算法
- [ ] CLI入口

### 3.3 形态识别 (pattern) 🔥 CORE
- [ ] 技术指标计算 (indicators.py)
- [ ] IPO底部检测器
- [ ] 突破扫描器
- [ ] 回测入场检测
- [ ] 真实股票测试 (CAVA等)

### 3.4 禁售期跟踪 (lockup)
- [ ] LockupEvent 管理
- [ ] 到期日历
- [ ] 供应冲击预警

### 3.5 情绪分析 (sentiment)
- [ ] 关键词情绪分析
- [ ] Ollama集成（可选）
- [ ] 情绪趋势计算

### 3.6 业绩追踪 (earnings)
- [ ] EarningsReport 解析
- [ ] 首次财报信号
- [ ] 财报日历

---

## Phase 4: 综合评分 (Day 15-16)

### 4.1 评分引擎
- [ ] SignalAggregator
- [ ] 四窗口状态整合
- [ ] 综合信号判定
- [ ] 风险因素识别

### 4.2 每日扫描
- [ ] DailyScanner
- [ ] 批量扫描
- [ ] 报告生成
- [ ] CLI入口

---

## Phase 5: 仪表盘 (Day 17-19)

### 5.1 Streamlit应用
- [ ] 主页 - 信号总览
- [ ] 信号表格
- [ ] 顶部统计卡片

### 5.2 个股详情
- [ ] K线图 (Plotly)
- [ ] 四窗口状态卡片
- [ ] 基本面雷达图
- [ ] 新闻情绪展示

### 5.3 IPO日历页
- [ ] 即将上市列表
- [ ] 禁售期到期列表
- [ ] 财报发布列表

### 5.4 侧边栏
- [ ] 观察名单管理
- [ ] 手动扫描按钮
- [ ] 刷新时间显示

---

## Phase 6: 自动化与通知 (Day 20-21)

### 6.1 定时任务
- [ ] 每日扫描调度
- [ ] 盘中突破检测
- [ ] 盘后形态更新
- [ ] 每周IPO日历更新

### 6.2 飞书通知
- [ ] FeishuNotifier
- [ ] Webhook配置
- [ ] 消息模板
- [ ] 通知触发规则

### 6.3 Docker部署
- [ ] Dockerfile
- [ ] docker-compose.yml
- [ ] 多服务编排

### 6.4 Makefile
- [ ] make setup
- [ ] make scan
- [ ] make dashboard
- [ ] make start

---

## 当前进度

```
总进度: ████░░░░░░░░░░░░░░░░ 20%
Phase 1: ████████████ 100% ✅
Phase 2: ░░░░░░░░░░░░ 0%
Phase 3: ░░░░░░░░░░░░ 0%
Phase 4: ░░░░░░░░░░░░ 0%
Phase 5: ░░░░░░░░░░░░ 0%
Phase 6: ░░░░░░░░░░░░ 0%
```

---

## 阻塞问题

暂无

---

## 下一步行动

1. 完成 Phase 1.1 - 项目初始化
2. 开始 Phase 1.2 - 爬虫基础组件
