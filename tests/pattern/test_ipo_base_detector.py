"""IPO底部形态检测器测试."""

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta

from src.pattern.ipo_base_detector import IPOBaseDetector, IPOBase


class TestIPOBaseDetector:
    """测试IPO底部形态检测器."""

    @pytest.fixture
    def detector(self):
        """创建检测器实例."""
        return IPOBaseDetector()

    @pytest.fixture
    def create_base_data(self):
        """创建底部形态测试数据."""
        def _create(days=100, ipo_price=100, left_high=120, base_low=105, end_price=118):
            dates = pd.date_range(start='2024-01-01', periods=days)
            
            # IPO初期上涨到左侧高点
            early_days = min(20, days // 5)
            early_prices = np.linspace(ipo_price, left_high, early_days)
            
            # 回调形成底部
            base_start = early_days
            base_days = days - early_days - 10
            base_prices_high = np.linspace(left_high, base_low + 5, base_days)
            base_prices_low = np.linspace(left_high - 5, base_low, base_days)
            
            # 最后上涨
            end_days = 10
            end_prices = np.linspace(end_price - 2, end_price, end_days)
            
            # 合并
            all_high = np.concatenate([
                early_prices + 2,
                base_prices_high,
                end_prices + 2
            ])
            all_low = np.concatenate([
                early_prices - 2,
                base_prices_low,
                end_prices - 2
            ])
            all_close = (all_high + all_low) / 2
            
            df = pd.DataFrame({
                'date': dates[:len(all_close)],
                'open': all_close - 0.5,
                'high': all_high[:len(all_close)],
                'low': all_low[:len(all_close)],
                'close': all_close,
                'volume': np.random.randint(1000000, 5000000, len(all_close)),
                'ticker': 'TEST'
            })
            
            return df
        
        return _create

    def test_detect_empty_dataframe(self, detector):
        """测试空DataFrame."""
        result = detector.detect(pd.DataFrame(), date(2024, 1, 1))
        
        assert result.has_base is False
        assert result.base_type == "unknown"

    def test_detect_short_dataframe(self, detector):
        """测试数据不足."""
        df = pd.DataFrame({
            'date': pd.date_range(start='2024-01-01', periods=5),
            'open': [100] * 5,
            'high': [105] * 5,
            'low': [95] * 5,
            'close': [100] * 5,
            'volume': [1000000] * 5,
        })
        
        result = detector.detect(df, date(2024, 1, 1))
        
        assert result.has_base is False

    def test_detect_flat_base(self, detector, create_base_data):
        """测试平底检测."""
        # 创建平底数据（浅回调 10-15%之间）
        df = create_base_data(
            days=100,
            ipo_price=100,
            left_high=115,  # 15%上涨
            base_low=102,   # 11%回调，在10-15%之间
            end_price=110
        )
        
        result = detector.detect(df, date(2024, 1, 1))
        
        assert result.has_base is True
        assert result.base_type == "flat"
        assert result.left_high is not None

    def test_detect_cup_base(self, detector, create_base_data):
        """测试杯型底检测."""
        # 创建杯型底数据（中等深度15-35%）
        df = create_base_data(
            days=100,
            ipo_price=100,
            left_high=130,  # 30%上涨
            base_low=100,   # 23%回调
            end_price=125
        )
        
        result = detector.detect(df, date(2024, 1, 1))
        
        assert result.has_base is True
        assert result.base_type in ["cup", "ascending_triangle", "unknown"]

    def test_detect_no_base_shallow_pullback(self, detector, create_base_data):
        """测试无底部（回调太浅）."""
        df = create_base_data(
            days=100,
            ipo_price=100,
            left_high=105,  # 仅5%上涨
            base_low=103,   # 不到10%深度
            end_price=104
        )
        
        result = detector.detect(df, date(2024, 1, 1))
        
        # 回调太浅，无法形成底部
        assert result.has_base is False

    def test_detect_no_base_deep_crash(self, detector, create_base_data):
        """测试无底部（跌幅过大）."""
        df = create_base_data(
            days=100,
            ipo_price=100,
            left_high=150,
            base_low=60,    # 60%回调，超过50%限制
            end_price=70
        )
        
        result = detector.detect(df, date(2024, 1, 1))
        
        # 跌幅过大，不构成有效底部
        assert result.has_base is False

    def test_base_calculations(self, detector, create_base_data):
        """测试底部计算字段."""
        df = create_base_data(days=100)
        
        result = detector.detect(df, date(2024, 1, 1))
        
        assert result.has_base is True
        assert result.base_depth_pct is not None
        assert result.base_length_days is not None
        assert result.base_length_days >= detector.MIN_BASE_DAYS
        assert result.left_high is not None
        assert result.base_start is not None

    def test_tightness_calculation(self, detector, create_base_data):
        """测试紧密度计算."""
        df = create_base_data(days=100)
        
        result = detector.detect(df, date(2024, 1, 1))
        
        if result.has_base:
            assert result.tightness is not None
            assert 0 <= result.tightness <= 1

    def test_volume_dry_up(self, detector, create_base_data):
        """测试成交量萎缩检测."""
        df = create_base_data(days=100)
        
        # 修改成交量，让底部期间成交量较低（转换为float）
        df['volume'] = df['volume'].astype(float)
        df.loc[20:80, 'volume'] = df.loc[20:80, 'volume'] * 0.3
        
        result = detector.detect(df, date(2024, 1, 1))
        
        if result.has_base:
            # 应该检测到成交量萎缩
            assert result.volume_dry_up == True

    def test_find_left_high(self, detector):
        """测试左侧高点查找."""
        df = pd.DataFrame({
            'date': pd.date_range(start='2024-01-01', periods=50),
            'open': [100] * 50,
            'high': [100, 105, 110, 108, 112, 115, 113, 118, 120, 119] + [110] * 40,
            'low': [95] * 50,
            'close': [100] * 50,
            'volume': [1000000] * 50,
        })
        
        idx, price = detector._find_left_high(df)
        
        # 应该找到120作为左侧高点
        assert price == 120
        assert idx is not None

    def test_classify_base_type_flat(self, detector):
        """测试平底分类."""
        # 创建平底数据
        dates = pd.date_range(start='2024-01-01', periods=30)
        df = pd.DataFrame({
            'date': dates,
            'high': [105] * 30,
            'low': [100] * 30,
        })
        
        base_type = detector._classify_base_type(df, left_high=110, base_low=100)
        
        assert base_type == "flat"

    def test_classify_base_type_cup(self, detector):
        """测试杯型分类."""
        # 创建杯型数据（U型底部）
        dates = pd.date_range(start='2024-01-01', periods=40)
        # U型：前半段下跌，后半段上涨
        high_values = list(range(120, 100, -1)) + list(range(100, 120))
        # 创建完整的OHLC数据
        df = pd.DataFrame({
            'date': dates[:len(high_values)],
            'high': high_values,
            'low': [h - 5 for h in high_values],
            'close': [h - 2.5 for h in high_values],
            'open': [h - 2.5 for h in high_values],
        })
        
        base_type = detector._classify_base_type(df, left_high=120, base_low=100)
        
        assert base_type in ["cup", "ascending_triangle", "unknown"]


class TestIPOBase:
    """测试IPOBase数据类."""

    def test_ipo_base_creation(self):
        """测试创建IPOBase."""
        base = IPOBase(
            ticker="TEST",
            has_base=True,
            base_type="flat",
            base_start=date(2024, 1, 1),
            base_end=date(2024, 3, 1),
            base_depth_pct=12.5,
            base_length_days=60,
            left_high=110.0,
            tightness=0.8,
            volume_dry_up=True,
        )
        
        assert base.ticker == "TEST"
        assert base.has_base is True
        assert base.base_type == "flat"
        assert base.base_depth_pct == 12.5

    def test_ipo_base_no_base(self):
        """测试无底部情况."""
        base = IPOBase(
            ticker="TEST",
            has_base=False,
            base_type="unknown",
        )
        
        assert base.has_base is False
        assert base.base_type == "unknown"
