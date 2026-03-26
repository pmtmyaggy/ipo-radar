#!/usr/bin/env python3
"""数据更新脚本 - 自动获取所有数据源的数据.

用法:
    python scripts/update_data.py

功能:
    1. 更新IPO日历
    2. 获取股价数据
    3. 获取S-1文件信息
    4. 获取机构持仓(13F)
    5. 获取新闻数据
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
env_path = project_root / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def update_ipo_calendar():
    """更新IPO日历."""
    logger.info("=" * 50)
    logger.info("1. 更新IPO日历...")
    
    try:
        from src.crawler.api import CrawlerAPI
        api = CrawlerAPI()
        count = api.refresh_ipo_calendar()
        logger.info(f"   ✅ 更新了 {count} 个IPO事件")
        return count
    except Exception as e:
        logger.error(f"   ❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()
        return 0


def update_stock_prices():
    """更新股价数据."""
    logger.info("=" * 50)
    logger.info("2. 更新股价数据...")
    
    try:
        # 从数据库获取所有股票
        import sqlite3
        conn = sqlite3.connect('data/ipo_radar.db')
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT ticker FROM stock_bars')
        tickers = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if not tickers:
            tickers = ['CAVA', 'AAPL', 'TSLA', 'NVDA', 'ARM']
        
        logger.info(f"   发现 {len(tickers)} 只股票")
        
        from src.crawler.market_data import MarketDataCrawler
        md = MarketDataCrawler()
        updated = 0
        
        for ticker in tickers[:10]:
            try:
                bars = md.fetch(ticker=ticker, start=date.today() - timedelta(days=30))
                if bars:
                    logger.info(f"   ✅ {ticker}: 获取 {len(bars)} 条数据")
                    updated += 1
                else:
                    logger.warning(f"   ⚠️  {ticker}: 无数据")
            except Exception as e:
                logger.error(f"   ❌ {ticker}: {e}")
        
        logger.info(f"   完成 {updated}/{len(tickers)} 只股票更新")
        return updated
        
    except Exception as e:
        logger.error(f"   ❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()
        return 0


def update_s1_filings():
    """更新S-1文件信息."""
    logger.info("=" * 50)
    logger.info("3. 更新S-1文件...")
    
    try:
        from src.crawler.edgar_monitor import EdgarIPOCrawler
        crawler = EdgarIPOCrawler()
        
        start_date = date.today() - timedelta(days=7)
        logger.info(f"   搜索从 {start_date} 开始的S-1文件...")
        
        filings = crawler.search_s1_filings(start_date=start_date, days=7)
        
        if filings:
            logger.info(f"   ✅ 找到 {len(filings)} 个S-1文件")
            for f in filings[:5]:
                logger.info(f"   - {f.get('company_name', 'N/A')}: {f.get('filed_date', 'N/A')}")
        else:
            logger.info("   ℹ️  未找到新的S-1文件")
        
        return len(filings)
        
    except Exception as e:
        logger.error(f"   ❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()
        return 0


def update_13f_holdings():
    """更新13F机构持仓."""
    logger.info("=" * 50)
    logger.info("4. 更新13F机构持仓...")
    
    try:
        from src.crawler.holdings_fetcher import HoldingsFetcher
        hf = HoldingsFetcher()
        
        logger.info("   ℹ️  13F数据需要手动获取")
        logger.info("   示例: 可通过 HoldingsFetcher 获取指定CIK的持仓")
        
        return 0
        
    except Exception as e:
        logger.error(f"   ❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()
        return 0


def update_news():
    """更新新闻数据."""
    logger.info("=" * 50)
    logger.info("5. 更新新闻数据...")
    
    try:
        from src.crawler.news_fetcher import NewsCrawler
        nc = NewsCrawler()
        
        tickers = ['CAVA', 'ARM', 'TSLA']
        total_news = 0
        
        for ticker in tickers:
            try:
                news = nc.fetch(ticker=ticker, days=7)
                if news:
                    logger.info(f"   ✅ {ticker}: 获取 {len(news)} 条新闻")
                    total_news += len(news)
                else:
                    logger.info(f"   ℹ️  {ticker}: 无新闻")
            except Exception as e:
                logger.error(f"   ❌ {ticker}: {e}")
        
        logger.info(f"   总共获取 {total_news} 条新闻")
        return total_news
        
    except Exception as e:
        logger.error(f"   ❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()
        return 0


def show_database_stats():
    """显示数据库统计."""
    logger.info("=" * 50)
    logger.info("数据库统计:")
    
    try:
        import sqlite3
        conn = sqlite3.connect('data/ipo_radar.db')
        cursor = conn.cursor()
        
        tables = [
            'ipo_events',
            'stock_bars',
            's1_filings',
            'institutional_holdings',
            'news_items',
            'earnings_reports',
            'lockup_info'
        ]
        
        for table in tables:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM {table}')
                count = cursor.fetchone()[0]
                logger.info(f"   {table}: {count} 条")
            except Exception as e:
                logger.warning(f"   {table}: 无法获取 - {e}")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"   统计失败: {e}")


def main():
    """主函数."""
    logger.info("🚀 开始数据更新...")
    logger.info(f"📅 当前日期: {date.today()}")
    
    # 确保数据库初始化
    try:
        from src.crawler.models.database import init_database
        init_database()
        logger.info("✅ 数据库初始化完成")
    except Exception as e:
        logger.warning(f"⚠️  数据库初始化: {e}")
    
    # 执行更新
    results = {
        "IPO日历": update_ipo_calendar(),
        "股价数据": update_stock_prices(),
        "S-1文件": update_s1_filings(),
        "13F持仓": update_13f_holdings(),
        "新闻数据": update_news(),
    }
    
    # 显示统计
    show_database_stats()
    
    # 总结
    logger.info("=" * 50)
    logger.info("📊 更新总结:")
    for name, count in results.items():
        logger.info(f"   {name}: {count}")
    
    logger.info("✅ 数据更新完成!")


if __name__ == "__main__":
    main()
