"""Pytest 配置和共享fixtures."""

import os
import tempfile
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 设置测试环境
os.environ["ENV"] = "testing"
os.environ["LOG_LEVEL"] = "DEBUG"


@pytest.fixture(scope="session")
def test_db_url():
    """创建临时测试数据库."""
    # 使用内存中的SQLite进行测试
    return "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_session(test_db_url):
    """创建测试数据库会话."""
    from src.crawler.models.database import Base
    
    engine = create_engine(test_db_url)
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_ipo_event():
    """示例IPO事件数据."""
    return {
        "ticker": "TEST",
        "company_name": "Test Company Inc.",
        "cik": "0001234567",
        "exchange": "NASDAQ",
        "expected_date": date(2024, 6, 15),
        "price_range_low": 15.0,
        "price_range_high": 18.0,
        "final_price": 17.0,
        "shares_offered": 10000000,
        "lead_underwriter": "Goldman Sachs",
        "status": "trading",
        "sector": "Technology",
    }


@pytest.fixture
def sample_stock_bars():
    """示例行情数据."""
    return [
        {
            "ticker": "TEST",
            "date": date(2024, 6, 15),
            "open": 17.0,
            "high": 18.5,
            "low": 16.8,
            "close": 18.2,
            "volume": 5000000,
        },
        {
            "ticker": "TEST",
            "date": date(2024, 6, 16),
            "open": 18.2,
            "high": 19.0,
            "low": 17.9,
            "close": 18.8,
            "volume": 3500000,
        },
    ]
