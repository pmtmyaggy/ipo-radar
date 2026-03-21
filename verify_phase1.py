#!/usr/bin/env python3
"""Phase 1 验证脚本.

验证所有基础组件是否可以正常导入和初始化。
"""

import sys
from datetime import date
from decimal import Decimal


def print_header(text: str):
    """打印标题."""
    print(f"\n{'='*60}")
    print(f" {text}")
    print(f"{'='*60}")


def print_success(text: str):
    """打印成功信息."""
    print(f"  ✓ {text}")


def print_error(text: str):
    """打印错误信息."""
    print(f"  ✗ {text}")


def verify_imports():
    """验证导入."""
    print_header("1. 验证模块导入")
    
    errors = []
    
    # 测试数据模型导入
    try:
        from src.crawler.models.schemas import (
            IPOEvent, StockBar, NewsItem, LockupInfo,
            QuickScore, IPOStatus, LockupStatus
        )
        print_success("schemas 模型导入成功")
    except Exception as e:
        print_error(f"schemas 导入失败: {e}")
        errors.append("schemas")
    
    # 测试数据库导入
    try:
        from src.crawler.models.database import (
            Base, IPOEventModel, DatabaseManager, init_database
        )
        print_success("database 模块导入成功")
    except Exception as e:
        print_error(f"database 导入失败: {e}")
        errors.append("database")
    
    # 测试爬虫基类导入
    try:
        from src.crawler.base import BaseCrawler
        print_success("base 模块导入成功")
    except Exception as e:
        print_error(f"base 导入失败: {e}")
        errors.append("base")
    
    # 测试工具函数导入
    try:
        from src.crawler.utils.rate_limiter import RateLimiter, AdaptiveRateLimiter
        from src.crawler.utils.retry import retry_with_backoff, RetryError
        from src.crawler.utils.user_agent import UserAgentManager
        print_success("utils 工具函数导入成功")
    except Exception as e:
        print_error(f"utils 导入失败: {e}")
        errors.append("utils")
    
    return len(errors) == 0


def verify_models():
    """验证数据模型."""
    print_header("2. 验证数据模型")
    
    from src.crawler.models.schemas import (
        IPOEvent, StockBar, QuickScore, IPOStatus
    )
    
    # 测试IPOEvent创建
    try:
        event = IPOEvent(
            ticker="TEST",
            company_name="Test Company",
            status=IPOStatus.TRADING,
            expected_date=date(2024, 6, 15),
            price_range_low=Decimal("15.00"),
        )
        assert event.ticker == "TEST"
        assert event.price_range_low == Decimal("15.00")
        print_success("IPOEvent 模型创建成功")
    except Exception as e:
        print_error(f"IPOEvent 创建失败: {e}")
        return False
    
    # 测试StockBar创建
    try:
        bar = StockBar(
            ticker="AAPL",
            date=date(2024, 1, 15),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.50"),
            close=Decimal("153.00"),
            volume=1000000,
        )
        assert bar.close == Decimal("153.00")
        print_success("StockBar 模型创建成功")
    except Exception as e:
        print_error(f"StockBar 创建失败: {e}")
        return False
    
    # 测试QuickScore创建
    try:
        score = QuickScore(
            ticker="TEST",
            total=75,
            details={"revenue": 25, "margin": 20},
            verdict="PASS",
        )
        assert score.total == 75
        print_success("QuickScore 模型创建成功")
    except Exception as e:
        print_error(f"QuickScore 创建失败: {e}")
        return False
    
    return True


def verify_utils():
    """验证工具函数."""
    print_header("3. 验证工具函数")
    
    from src.crawler.utils.rate_limiter import RateLimiter
    from src.crawler.utils.user_agent import UserAgentManager
    
    # 测试RateLimiter
    try:
        limiter = RateLimiter(rate=5.0, burst=3)
        # 应该可以获得3个令牌
        count = 0
        for _ in range(3):
            if limiter.acquire(blocking=False):
                count += 1
        assert count == 3
        print_success("RateLimiter 工作正常")
    except Exception as e:
        print_error(f"RateLimiter 测试失败: {e}")
        return False
    
    # 测试UserAgentManager
    try:
        manager = UserAgentManager(contact_email="test@example.com")
        ua = manager.get_standard()
        assert "IPO-Radar" in ua
        assert "test@example.com" in ua
        
        headers = manager.get_headers()
        assert "User-Agent" in headers
        print_success("UserAgentManager 工作正常")
    except Exception as e:
        print_error(f"UserAgentManager 测试失败: {e}")
        return False
    
    return True


def verify_database():
    """验证数据库功能."""
    print_header("4. 验证数据库功能")
    
    from src.crawler.models.database import init_database, DatabaseManager
    import tempfile
    import os
    
    try:
        # 使用临时数据库测试
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            
            # 初始化数据库
            manager = init_database(db_url)
            
            # 验证数据库文件创建
            assert os.path.exists(db_path)
            print_success("数据库初始化成功")
            
            # 验证可以创建会话
            session = manager.get_session()
            assert session is not None
            session.close()
            print_success("数据库会话创建成功")
            
    except Exception as e:
        print_error(f"数据库测试失败: {e}")
        return False
    
    return True


def verify_file_structure():
    """验证文件结构."""
    print_header("5. 验证文件结构")
    
    import os
    
    required_files = [
        "pyproject.toml",
        ".env.example",
        "README.md",
        ".gitignore",
        "src/crawler/models/schemas.py",
        "src/crawler/models/database.py",
        "src/crawler/base.py",
        "src/crawler/utils/rate_limiter.py",
        "src/crawler/utils/retry.py",
        "src/crawler/utils/user_agent.py",
    ]
    
    missing = []
    for file in required_files:
        if not os.path.exists(file):
            missing.append(file)
            print_error(f"缺少文件: {file}")
        else:
            print_success(f"文件存在: {file}")
    
    return len(missing) == 0


def main():
    """主函数."""
    print("\n" + "="*60)
    print(" IPO-Radar Phase 1 验证")
    print("="*60)
    
    results = []
    
    # 运行所有验证
    results.append(("模块导入", verify_imports()))
    results.append(("数据模型", verify_models()))
    results.append(("工具函数", verify_utils()))
    results.append(("数据库功能", verify_database()))
    results.append(("文件结构", verify_file_structure()))
    
    # 汇总结果
    print_header("验证结果汇总")
    
    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print(" 🎉 Phase 1 验证全部通过！")
        print("="*60)
        return 0
    else:
        print(" ⚠️ 部分验证未通过，请检查错误信息")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
