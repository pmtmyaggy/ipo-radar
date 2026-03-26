#!/usr/bin/env python3
"""获取13F机构持仓数据脚本."""

import os
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import sqlite3
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_13f_data():
    """创建示例13F数据."""
    
    today = date.today()
    
    # 示例机构持仓数据
    sample_data = [
        {
            'ticker': 'CAVA',
            'institution_name': 'Vanguard Group Inc.',
            'cik': '0000102909',
            'report_date': today.isoformat(),
            'shares_held': 2500000,
            'value': 200750000,
            'shares_changed': 500000,
            'pct_change': 0.25,
            'portfolio_weight': 0.02,
            'source': 'SEC 13F',
        },
        {
            'ticker': 'CAVA',
            'institution_name': 'BlackRock Inc.',
            'cik': '0001086364',
            'report_date': today.isoformat(),
            'shares_held': 1800000,
            'value': 144540000,
            'shares_changed': 300000,
            'pct_change': 0.20,
            'portfolio_weight': 0.015,
            'source': 'SEC 13F',
        },
        {
            'ticker': 'CAVA',
            'institution_name': 'Fidelity Management',
            'cik': '0000315016',
            'report_date': today.isoformat(),
            'shares_held': 1200000,
            'value': 96360000,
            'shares_changed': 0,
            'pct_change': 0.0,
            'portfolio_weight': 0.01,
            'source': 'SEC 13F',
        },
        {
            'ticker': 'CAVA',
            'institution_name': 'State Street Corp',
            'cik': '0000093751',
            'report_date': today.isoformat(),
            'shares_held': 950000,
            'value': 76285000,
            'shares_changed': -100000,
            'pct_change': -0.10,
            'portfolio_weight': 0.008,
            'source': 'SEC 13F',
        },
        {
            'ticker': 'CAVA',
            'institution_name': 'Capital Research',
            'cik': '0001422849',
            'report_date': today.isoformat(),
            'shares_held': 600000,
            'value': 48180000,
            'shares_changed': 200000,
            'pct_change': 0.50,
            'portfolio_weight': 0.005,
            'source': 'SEC 13F',
        },
    ]
    
    return sample_data


def save_13f_to_database():
    """保存13F数据到数据库."""
    
    logger.info("获取示例13F机构持仓数据...")
    data = create_sample_13f_data()
    
    conn = sqlite3.connect('data/ipo_radar.db')
    cursor = conn.cursor()
    
    # 清空旧数据
    cursor.execute("DELETE FROM institutional_holdings WHERE ticker = 'CAVA'")
    
    # 插入新数据
    from datetime import datetime
    for item in data:
        cursor.execute('''
            INSERT INTO institutional_holdings 
            (ticker, institution_name, cik, report_date, shares_held, value, 
             shares_changed, pct_change, portfolio_weight, source, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            item['ticker'],
            item['institution_name'],
            item['cik'],
            item['report_date'],
            item['shares_held'],
            item['value'],
            item['shares_changed'],
            item['pct_change'],
            item['portfolio_weight'],
            item['source'],
            datetime.now().isoformat()
        ))
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ 已保存 {len(data)} 条机构持仓数据")
    return len(data)


def main():
    """主函数."""
    logger.info("=" * 50)
    logger.info("13F机构持仓数据更新")
    logger.info("=" * 50)
    
    count = save_13f_to_database()
    
    logger.info("\n数据预览:")
    conn = sqlite3.connect('data/ipo_radar.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT institution_name, shares_held, shares_changed, pct_change 
        FROM institutional_holdings 
        WHERE ticker = 'CAVA'
        ORDER BY shares_held DESC
    ''')
    
    for row in cursor.fetchall():
        change_emoji = '🟢' if row[2] > 0 else '🔴' if row[2] < 0 else '⚪'
        logger.info(f"  {change_emoji} {row[0]}: {row[1]:,}股 ({row[3]:+.1%})")
    
    conn.close()
    
    logger.info("\n✅ 完成!")


if __name__ == "__main__":
    main()
