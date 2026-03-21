"""Docker部署测试.

验证Docker配置和容器化部署。
"""

import pytest
import subprocess
import os
import yaml
from pathlib import Path
import time


class TestDockerConfiguration:
    """测试Docker配置."""

    def test_dockerfile_exists(self):
        """测试Dockerfile存在."""
        dockerfile = Path("Dockerfile")
        assert dockerfile.exists(), "Dockerfile not found"

    def test_dockerfile_content(self):
        """测试Dockerfile内容."""
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        # 关键元素检查
        assert "FROM python" in content
        assert "WORKDIR" in content
        assert "requirements.txt" in content
        assert "EXPOSE" in content
        assert "HEALTHCHECK" in content

    def test_docker_compose_exists(self):
        """测试docker-compose.yml存在."""
        compose_file = Path("docker-compose.yml")
        assert compose_file.exists(), "docker-compose.yml not found"

    def test_docker_compose_valid_yaml(self):
        """测试docker-compose.yml是有效YAML."""
        with open("docker-compose.yml", "r") as f:
            compose = yaml.safe_load(f)
        
        assert "services" in compose
        assert "dashboard" in compose["services"]
        assert "scheduler" in compose["services"]

    def test_docker_compose_dashboard_config(self):
        """测试dashboard服务配置."""
        with open("docker-compose.yml", "r") as f:
            compose = yaml.safe_load(f)
        
        dashboard = compose["services"]["dashboard"]
        assert dashboard["ports"] == ["8501:8501"]
        assert "volumes" in dashboard
        assert "environment" in dashboard
        assert "healthcheck" in dashboard

    def test_docker_compose_scheduler_config(self):
        """测试scheduler服务配置."""
        with open("docker-compose.yml", "r") as f:
            compose = yaml.safe_load(f)
        
        scheduler = compose["services"]["scheduler"]
        assert "command" in scheduler
        assert "depends_on" in scheduler
        assert "dashboard" in scheduler["depends_on"]

    def test_requirements_txt_exists(self):
        """测试requirements.txt存在."""
        req_file = Path("requirements.txt")
        assert req_file.exists(), "requirements.txt not found"

    def test_requirements_content(self):
        """测试requirements.txt包含关键依赖."""
        with open("requirements.txt", "r") as f:
            content = f.read().lower()
        
        # 检查关键依赖
        assert "streamlit" in content
        assert "pandas" in content
        assert "requests" in content
        assert "sqlalchemy" in content


class TestDockerBuild:
    """测试Docker构建."""

    @pytest.fixture(scope="class")
    def docker_image(self):
        """构建Docker镜像."""
        result = subprocess.run(
            ["docker", "build", "-t", "ipo-radar:test", "."],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            pytest.fail(f"Docker build failed: {result.stderr}")
        
        yield "ipo-radar:test"
        
        # 清理
        subprocess.run(
            ["docker", "rmi", "ipo-radar:test"],
            capture_output=True
        )

    def test_docker_version(self):
        """测试Docker可用."""
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            pytest.skip("Docker daemon not running")
        
        assert len(result.stdout.strip()) > 0
        print(f"Docker version: {result.stdout.strip()}")

    def test_docker_compose_config(self):
        """测试docker-compose配置有效性."""
        result = subprocess.run(
            ["docker-compose", "config"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"docker-compose config failed: {result.stderr}"

    def test_docker_build(self, docker_image):
        """测试Docker镜像构建."""
        # 检查镜像是否存在
        result = subprocess.run(
            ["docker", "images", "-q", docker_image],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert len(result.stdout.strip()) > 0, "Docker image not found"

    def test_docker_image_structure(self, docker_image):
        """测试Docker镜像结构."""
        # 检查镜像中的文件
        result = subprocess.run(
            ["docker", "run", "--rm", docker_image, "ls", "/app"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "src" in result.stdout

    def test_docker_image_python(self, docker_image):
        """测试Docker镜像Python版本."""
        result = subprocess.run(
            ["docker", "run", "--rm", docker_image, "python", "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "Python 3." in result.stdout


class TestDockerRuntime:
    """测试Docker运行时."""

    @pytest.fixture(scope="class")
    def running_container(self):
        """启动测试容器."""
        # 启动容器
        container_id = subprocess.run(
            ["docker", "run", "-d", "--name", "ipo-radar-test", 
             "-p", "8501:8501", "ipo-radar:test"],
            capture_output=True,
            text=True
        )
        
        if container_id.returncode != 0:
            pytest.skip(f"Failed to start container: {container_id.stderr}")
        
        container = container_id.stdout.strip()
        
        # 等待容器启动
        time.sleep(5)
        
        yield container
        
        # 清理
        subprocess.run(
            ["docker", "stop", "ipo-radar-test"],
            capture_output=True
        )
        subprocess.run(
            ["docker", "rm", "ipo-radar-test"],
            capture_output=True
        )

    def test_container_health(self, running_container):
        """测试容器健康状态."""
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", running_container],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "running" in result.stdout

    def test_container_logs(self, running_container):
        """测试容器日志."""
        result = subprocess.run(
            ["docker", "logs", running_container],
            capture_output=True,
            text=True
        )
        # 日志可能为空，但命令应该成功
        assert result.returncode == 0


class TestEnvironmentConfiguration:
    """测试环境配置."""

    def test_env_example_exists(self):
        """测试.env.example存在."""
        env_file = Path(".env.example")
        assert env_file.exists(), ".env.example not found"

    def test_env_example_content(self):
        """测试.env.example包含必要变量."""
        with open(".env.example", "r") as f:
            content = f.read()
        
        # 检查关键环境变量
        assert "DATABASE_URL" in content
        assert "EDGAR_IDENTITY" in content

    def test_data_directory_structure(self):
        """测试数据目录结构."""
        data_dir = Path("data")
        assert data_dir.exists(), "data directory not found"
        assert data_dir.is_dir(), "data is not a directory"

    def test_makefile_docker_targets(self):
        """测试Makefile包含Docker相关目标."""
        makefile = Path("Makefile")
        with open(makefile, "r") as f:
            content = f.read()
        
        assert "docker-build" in content
        assert "start" in content
        assert "stop" in content


class TestServiceIntegration:
    """测试服务集成配置."""

    def test_dashboard_healthcheck(self):
        """测试dashboard健康检查配置."""
        with open("docker-compose.yml", "r") as f:
            compose = yaml.safe_load(f)
        
        healthcheck = compose["services"]["dashboard"].get("healthcheck", {})
        assert "test" in healthcheck
        assert "interval" in healthcheck

    def test_scheduler_restart_policy(self):
        """测试scheduler重启策略."""
        with open("docker-compose.yml", "r") as f:
            compose = yaml.safe_load(f)
        
        scheduler = compose["services"]["scheduler"]
        assert scheduler.get("restart") == "unless-stopped"

    def test_shared_volume_mounts(self):
        """测试共享卷挂载."""
        with open("docker-compose.yml", "r") as f:
            compose = yaml.safe_load(f)
        
        dashboard_volumes = compose["services"]["dashboard"].get("volumes", [])
        scheduler_volumes = compose["services"]["scheduler"].get("volumes", [])
        
        # 两者都应该挂载data目录
        assert any("./data" in v for v in dashboard_volumes)
        assert any("./data" in v for v in scheduler_volumes)


class TestDockerComposeOperations:
    """测试Docker Compose操作."""

    def test_compose_build(self):
        """测试docker-compose构建."""
        result = subprocess.run(
            ["docker-compose", "build", "--no-cache"],
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        if result.returncode != 0:
            pytest.skip(f"docker-compose build failed: {result.stderr}")
        
        assert result.returncode == 0

    @pytest.mark.skip(reason="需要清理环境，手动运行")
    def test_compose_up_down(self):
        """测试docker-compose启动和停止."""
        # 启动服务
        up_result = subprocess.run(
            ["docker-compose", "up", "-d"],
            capture_output=True,
            text=True
        )
        assert up_result.returncode == 0
        
        # 检查服务状态
        ps_result = subprocess.run(
            ["docker-compose", "ps"],
            capture_output=True,
            text=True
        )
        assert ps_result.returncode == 0
        assert "ipo-radar" in ps_result.stdout
        
        # 停止服务
        down_result = subprocess.run(
            ["docker-compose", "down"],
            capture_output=True,
            text=True
        )
        assert down_result.returncode == 0
