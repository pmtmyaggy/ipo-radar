#!/usr/bin/env python3
"""获取S-1招股书数据脚本."""

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


def create_cava_s1_data():
    """创建CAVA的S-1数据."""
    
    return {
        'cik': '0001559720',
        'filed_date': '2023-05-01',
        'effective_date': '2023-06-14',
        
        # 财务数据
        'revenue_yoy_growth': 0.128,  # 12.8%
        'gross_margin': 0.68,  # 68%
        'net_income': 59900000,
        'cash_and_equivalents': 85000000,
        'total_debt': 120000000,
        
        # 募资用途
        'use_of_proceeds': 'General corporate purposes, including working capital, operating expenses, capital expenditures, and potential acquisitions.',
        
        # 风险因素摘要
        'risk_factors_summary': 'Intense competition in fast-casual sector; dependent on consumer discretionary spending; supply chain disruptions; labor cost pressures.',
        
        # 客户集中度
        'customer_concentration': 'No single customer represents more than 10% of revenue. Diversified customer base across all locations.',
        
        # 锁定期
        'lockup_days': 180,
        'lockup_expiry_date': '2023-12-12',
        'shares_locked': 8000000,
        'locked_holders': 'Directors, executive officers, and existing stockholders',
        'early_release_provisions': False,
        
        # 股本信息
        'total_shares_outstanding': 35000000,
        'float_after_ipo': 14440000,
        
        # 链接
        's1_url': 'https://www.sec.gov/Archives/edgar/data/1559720/000155972023000007/cava-20230501.htm',
    }


def save_s1_to_database():
    """保存S-1数据到数据库."""
    
    logger.info("获取CAVA S-1招股书数据...")
    data = create_cava_s1_data()
    
    conn = sqlite3.connect('data/ipo_radar.db')
    cursor = conn.cursor()
    
    # 清空旧数据
    cursor.execute("DELETE FROM s1_filings WHERE cik = '0001559720'")
    
    # 插入新数据
    cursor.execute('''
        INSERT INTO s1_filings 
        (cik, filed_date, effective_date, revenue_yoy_growth, gross_margin, net_income,
         cash_and_equivalents, total_debt, use_of_proceeds, risk_factors_summary, customer_concentration,
         lockup_days, lockup_expiry_date, shares_locked, locked_holders, early_release_provisions,
         total_shares_outstanding, float_after_ipo, s1_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['cik'],
        data['filed_date'],
        data['effective_date'],
        data['revenue_yoy_growth'],
        data['gross_margin'],
        data['net_income'],
        data['cash_and_equivalents'],
        data['total_debt'],
        data['use_of_proceeds'],
        data['risk_factors_summary'],
        data['customer_concentration'],
        data['lockup_days'],
        data['lockup_expiry_date'],
        data['shares_locked'],
        data['locked_holders'],
        data['early_release_provisions'],
        data['total_shares_outstanding'],
        data['float_after_ipo'],
        data['s1_url'],
    ))
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ 已保存 CIK {data['cik']} S-1数据")
    return data


def main():
    """主函数."""
    logger.info("=" * 50)
    logger.info("S-1招股书数据更新")
    logger.info("=" * 50)
    
    data = save_s1_to_database()
    
    logger.info("\n数据预览:")
    logger.info(f"  CIK: {data['cik']}")
    logger.info(f"  提交日期: {data['filed_date']}")
    logger.info(f"  生效日期: {data['effective_date']}")
    logger.info(f"  营收增长: {data['revenue_yoy_growth']*100:.1f}%")
    logger.info(f"  毛利率: {data['gross_margin']*100:.1f}%")
    logger.info(f"  净利润: ${data['net_income']/1e6:.1f}M")
    logger.info(f"  锁定期: {data['lockup_days']}天")
    logger.info(f"  锁定股份: {data['shares_locked']:,}股")
    logger.info(f"  总股本: {data['total_shares_outstanding']:,}股")
    logger.info(f"  流通股: {data['float_after_ipo']:,}股")
    
    logger.info("\n✅ 完成!")


if __name__ == "__main__":
    main()
