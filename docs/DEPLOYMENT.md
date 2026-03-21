# IPO-Radar 部署指南

## 系统要求

- Python 3.11+
- Docker & Docker Compose (可选，用于容器化部署)
- 4GB+ RAM
- 10GB+ 磁盘空间

## 本地部署

### 1. 克隆项目

```bash
git clone <repository-url>
cd ipo-radar
```

### 2. 环境配置

复制环境变量示例文件并配置：

```bash
cp .env.example .env
# 编辑 .env 文件，填入必要的配置
```

必需配置项：
- `EDGAR_IDENTITY`: SEC EDGAR API身份标识（格式：Name email@domain.com）
- `FEISHU_WEBHOOK_URL` (可选): 飞书通知Webhook地址

### 3. 安装依赖

```bash
make install
# 或
pip install -r requirements.txt
```

### 4. 初始化数据库

```bash
make setup
```

### 5. 运行测试

```bash
make test
```

### 6. 启动服务

启动仪表盘：
```bash
make dashboard
# 访问 http://localhost:8501
```

运行单次扫描：
```bash
make scan
```

启动定时任务：
```bash
make scheduler
```

## Docker部署

### 快速启动

```bash
# 构建镜像
make docker-build

# 启动所有服务
make start

# 查看日志
make logs

# 停止服务
make stop
```

### 手动Docker部署

```bash
# 构建
docker-compose build

# 启动
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

### 服务说明

- **dashboard**: Streamlit仪表盘 (端口: 8501)
- **scheduler**: 定时任务调度器

## 生产环境部署

### 1. 数据库优化

```python
from src.crawler.models.database import DatabaseManager
from src.crawler.models.indexes import create_indexes, optimize_database

db = DatabaseManager()
create_indexes(db)
optimize_database(db)
```

### 2. 配置日志轮转

在 `docker-compose.yml` 中添加：

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### 3. 设置监控

健康检查端点：
- Dashboard: http://localhost:8501

### 4. 备份策略

```bash
# 手动备份
make backup

# 自动备份脚本 (添加到crontab)
0 2 * * * cd /path/to/ipo-radar && make backup
```

## 故障排除

### 数据库锁定

如果遇到数据库锁定错误：

```bash
# 停止所有服务
make stop

# 删除锁定文件
rm data/ipo_radar.db-journal

# 重启
make start
```

### 内存不足

减少缓存大小或增加系统内存：

```python
# 在 .env 中设置
CACHE_SIZE=500
```

### 网络问题

检查代理设置：

```bash
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
```

## 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建
docker-compose build --no-cache

# 重启服务
docker-compose up -d
```

## 安全建议

1. **修改默认端口**: 在生产环境中修改默认端口
2. **启用HTTPS**: 使用反向代理（如Nginx）启用HTTPS
3. **限制访问**: 使用防火墙限制访问IP
4. **定期更新**: 定期更新依赖包
5. **监控日志**: 定期检查日志文件

## 支持

遇到问题请查看：
- [GitHub Issues](https://github.com/your-repo/ipo-radar/issues)
- 文档: `docs/API.md`
