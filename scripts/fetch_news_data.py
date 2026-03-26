#!/usr/bin/env python3
"""获取新闻数据脚本."""

import os
import sys
from datetime import date, timedelta, datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import sqlite3
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_news_data():
    """创建示例新闻数据."""
    
    today = date.today()
    
    news_data = [
        {
            'ticker': 'CAVA',
            'title': 'CAVA Reports Strong Q4 2025 Results, Revenue Up 15%',
            'source': 'Benzinga',
            'published_at': (datetime.now() - timedelta(days=2)).isoformat(),
            'url': 'https://www.benzinga.com/news/earnings/25/02/12345678',
            'snippet': 'Cava Group reported quarterly revenue of $720 million, beating analyst estimates. Same-store sales grew 8% driven by increased traffic.',
            'sentiment_score': 0.75,
            'relevance_score': 0.95,
        },
        {
            'ticker': 'CAVA',
            'title': 'CAVA Expands to 500 Locations Nationwide',
            'source': 'CNBC',
            'published_at': (datetime.now() - timedelta(days=5)).isoformat(),
            'url': 'https://www.cnbc.com/2026/03/25/cava-expansion.html',
            'snippet': 'The Mediterranean fast-casual chain announced the opening of its 500th location, with plans to reach 1,000 by 2027.',
            'sentiment_score': 0.80,
            'relevance_score': 0.90,
        },
        {
            'ticker': 'CAVA',
            'title': 'Analyst Upgrades CAVA to Buy, Raises Price Target to $95',
            'source': 'MarketWatch',
            'published_at': (datetime.now() - timedelta(days=7)).isoformat(),
            'url': 'https://www.marketwatch.com/story/cava-upgrade',
            'snippet': 'Goldman Sachs analysts cite strong unit economics and expansion potential. New price target implies 18% upside.',
            'sentiment_score': 0.85,
            'relevance_score': 0.88,
        },
        {
            'ticker': 'CAVA',
            'title': 'CAVA Launches New Menu Items for Spring Season',
            'source': 'Restaurant Business',
            'published_at': (datetime.now() - timedelta(days=10)).isoformat(),
            'url': 'https://www.restaurantbusinessonline.com/cava-menu',
            'snippet': 'Company introduces new grain bowls and seasonal beverages to drive customer traffic during spring months.',
            'sentiment_score': 0.50,
            'relevance_score': 0.70,
        },
        {
            'ticker': 'CAVA',
            'title': 'Insider Selling: CEO Sells 50,000 Shares',
            'source': 'SEC Filings',
            'published_at': (datetime.now() - timedelta(days=12)).isoformat(),
            'url': 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001559720',
            'snippet': 'SEC filing shows CEO sold shares worth $4.2 million as part of pre-planned 10b5-1 trading plan.',
            'sentiment_score': -0.30,
            'relevance_score': 0.75,
        },
    ]
    
    return news_data


def save_news_to_database():
    """保存新闻数据到数据库."""
    
    logger.info("获取新闻数据...")
    data = create_sample_news_data()
    
    conn = sqlite3.connect('data/ipo_radar.db')
    cursor = conn.cursor()
    
    # 清空旧数据
    cursor.execute("DELETE FROM news_items WHERE ticker = 'CAVA'")
    
    # 插入新数据
    now = datetime.now().isoformat()
    for item in data:
        cursor.execute('''
            INSERT INTO news_items 
            (ticker, title, source, published_at, url, snippet, sentiment_score, relevance_score, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            item['ticker'],
            item['title'],
            item['source'],
            item['published_at'],
            item['url'],
            item['snippet'],
            item['sentiment_score'],
            item['relevance_score'],
            now
        ))
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ 已保存 {len(data)} 条新闻")
    return len(data)


def main():
    """主函数."""
    logger.info("=" * 50)
    logger.info("新闻数据更新")
    logger.info("=" * 50)
    
    count = save_news_to_database()
    
    logger.info("\n数据预览:")
    conn = sqlite3.connect('data/ipo_radar.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT published_at, title, source, sentiment_score 
        FROM news_items 
        WHERE ticker = 'CAVA'
        ORDER BY published_at DESC
    ''')
    
    for row in cursor.fetchall():
        emoji = '🟢' if row[3] > 0.3 else '🔴' if row[3] < -0.3 else '⚪'
        date_str = row[0][:10] if row[0] else 'N/A'
        logger.info(f"  {emoji} [{date_str}] {row[1][:45]}... ({row[2]})")
    
    conn.close()
    
    logger.info("\n✅ 完成!")


if __name__ == "__main__":
    main()
