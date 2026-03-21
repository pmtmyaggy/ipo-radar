# IPO-Radar Makefile

.PHONY: help install setup test lint format clean dashboard scan scheduler docker-build docker-run docker-stop start stop logs migrate backup docs profile score

# 默认目标
help:
	@echo "IPO-Radar 可用命令:"
	@echo "  make install        安装依赖"
	@echo "  make setup          初始化项目"
	@echo "  make test           运行测试"
	@echo "  make lint           代码检查"
	@echo "  make format         格式化代码"
	@echo "  make dashboard      启动仪表盘"
	@echo "  make scan           运行每日扫描"
	@echo "  make scheduler      启动定时任务"
	@echo "  make clean          清理临时文件"
	@echo "  make docker-build   构建Docker镜像"
	@echo "  make start          启动所有服务 (Docker)"
	@echo "  make stop           停止所有服务 (Docker)"
	@echo "  make docker-build   构建Docker镜像"
	@echo "  make docker-run     运行Docker容器 (同 start)"
	@echo "  make docker-stop    停止Docker容器 (同 stop)"

# 安装依赖
install:
	pip install -r requirements.txt
	@echo "✅ 依赖安装完成"

# 项目初始化
setup:
	@echo "🚀 初始化 IPO-Radar..."
	mkdir -p data
	python -c "from src.crawler.models.database import init_database; init_database()"
	@echo "✅ 数据库初始化完成"
	@echo "⚠️ 请复制 .env.example 为 .env 并填写配置"

# 运行测试
test:
	pytest tests/ -v --cov=src --cov-report=html
	@echo "✅ 测试完成，报告在 htmlcov/ 目录"

# 代码检查
lint:
	ruff check src/
	mypy src/
	@echo "✅ 代码检查完成"

# 格式化代码
format:
	black src/ tests/
	ruff check --fix src/
	@echo "✅ 代码格式化完成"

# 启动仪表盘
dashboard:
	@echo "🚀 启动 Streamlit 仪表盘..."
	streamlit run src/dashboard/app.py

# 运行每日扫描
scan:
	@echo "🔄 运行每日扫描..."
	python -m src.scorer --scan --save

# 启动定时任务
scheduler:
	@echo "⏰ 启动定时任务..."
	python -m src.scheduler

# 分析单个股票
score:
	@read -p "输入股票代码: " ticker; \
	python -m src.scorer --ticker $$ticker

# 清理临时文件
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache htmlcov 2>/dev/null || true
	@echo "✅ 清理完成"

# Docker 构建
docker-build:
	docker build -t ipo-radar:latest .
	@echo "✅ Docker镜像构建完成"

# 启动所有服务 (Docker Compose)
start:
	@echo "🚀 启动所有服务..."
	docker-compose up -d
	@echo "✅ 所有服务已启动"
	@echo "  - Dashboard: http://localhost:8501"
	@echo "  - Scheduler: running in background"

# 停止所有服务
stop:
	@echo "🛑 停止所有服务..."
	docker-compose down
	@echo "✅ 所有服务已停止"

# Docker 运行 (别名)
docker-run: start

# Docker 停止 (别名)
docker-stop: stop

# Docker 停止
docker-stop:
	docker-compose down
	@echo "✅ Docker容器已停止"

# 查看日志
logs:
	docker-compose logs -f

# 数据库迁移（预留）
migrate:
	@echo "🔄 运行数据库迁移..."
	# alembic upgrade head

# 数据备份
backup:
	@mkdir -p backups
	@cp data/ipo_radar.db backups/ipo_radar_$(shell date +%Y%m%d_%H%M%S).db
	@echo "✅ 数据库已备份到 backups/ 目录"

# 生成文档
docs:
	@echo "📚 生成文档..."
	# 预留文档生成命令

# 性能分析
profile:
	@echo "📊 运行性能分析..."
	python -m cProfile -o profile.stats -m src.scorer --scan
