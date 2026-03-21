"""突破扫描器测试."""

import pytest
import pandas as pd
import numpy as np
from datetime import date

from src.pattern.breakout_scanner import BreakoutScanner, BreakoutSignal, PatternRecognizer
from src.pattern.ipo_base_detector import IPOBase, IPOBaseDetector


class TestBreakoutScanner:
    """测试突破扫描器."""

    @pytest.fixture
    def scanner(self):
        """创建扫描器实例."""
        return BreakoutScanner()

    @pytest.fixture
    def create_breakout_data(self):
        """创建突破测试数据."""
        def _create(days=60, left_high=120, breakout_day=45, volume_spike=True):
            dates = pd.date_range(start='2024-01-01', periods=days)
            
            # 确保 breakout_day 不超过 days
            breakout_day = min(breakout_day, days - 1)
            
            # IPO初期
            early = np.linspace(100, left_high - 5, 20)
            
            # 底部盘整
            base_days = max(1, breakout_day - 20)
            base_high = [left_high - 2] * base_days
            base_low = [left_high - 15] * base_days
            
            # 突破日
            if breakout_day < days:
                breakout_high = [left_high + 5]
                breakout_close = [left_high + 3]
            else:
                breakout_high = []
                breakout_close = []
            
            # 突破后
            remaining = max(0, days - breakout_day - 1)
            if remaining > 0:
                post_breakout = np.linspace(left_high + 3, left_high + 10, remaining)
            else:
                post_breakout = np.array([])
            
            # 合并价格
            base_closes = [(base_high[i] + base_low[i]) / 2 for i in range(base_days)]
            all_close = np.concatenate([
                early,
                base_closes,
                breakout_close,
                post_breakout if len(post_breakout) > 0 else []
            ])
            
            all_high = np.concatenate([
                early + 2,
                base_high,
                breakout_high,
                post_breakout + 2 if len(post_breakout) > 0 else []
            ])
            
            all_low = np.concatenate([
                early - 2,
                base_low,
                [left_high] if breakout_high else [],
                post_breakout - 2 if len(post_breakout) > 0 else []
            ])
            
            # 成交量
            base_volume = 1000000
            if volume_spike and breakout_day < days:
                volumes = [base_volume] * breakout_day + [base_volume * 2.5] + [base_volume * 1.5] * remaining
            else:
                volumes = [base_volume] * days
            
            # 确保长度一致
            min_len = min(len(all_close), len(volumes))
            all_close = all_close[:min_len]
            all_high = all_high[:min_len]
            all_low = all_low[:min_len]
            volumes = volumes[:min_len]
            dates = dates[:min_len]
            
            df = pd.DataFrame({
                'date': dates,
                'open': all_close - 0.5,
                'high': all_high,
                'low': all_low,
                'close': all_close,
                'volume': volumes,
            })
            
            return df
        
        return _create

    @pytest.fixture
    def base_info(self):
        """创建底部信息."""
        return IPOBase(
            ticker="TEST",
            has_base=True,
            base_type="flat",
            base_start=date(2024, 1, 15),
            base_end=date(2024, 3, 1),
            base_depth_pct=15.0,
            base_length_days=45,
            left_high=120.0,
            tightness=0.75,
            volume_dry_up=True,
        )

    def test_scan_no_base(self, scanner):
        """测试无底部时不检测."""
        df = pd.DataFrame({
            'date': pd.date_range(start='2024-01-01', periods=30),
            'open': [100] * 30,
            'high': [105] * 30,
            'low': [95] * 30,
            'close': [100] * 30,
            'volume': [1000000] * 30,
        })
        
        base = IPOBase(ticker="TEST", has_base=False, base_type="unknown")
        result = scanner.scan(df, base)
        
        assert result.breakout_detected is False

    def test_scan_strong_breakout(self, scanner, create_breakout_data, base_info):
        """测试强势突破检测."""
        df = create_breakout_data(days=60, left_high=120, breakout_day=45, volume_spike=True)
        
        result = scanner.scan(df, base_info)
        
        assert result.breakout_detected is True
        assert result.breakout_price is not None
        assert result.volume_confirmation == True

    def test_scan_weak_breakout_no_volume(self, scanner, create_breakout_data, base_info):
        """测试无量突破（弱势）."""
        df = create_breakout_data(days=60, left_high=120, breakout_day=45, volume_spike=False)
        
        result = scanner.scan(df, base_info)
        
        if result.breakout_detected:
            assert result.volume_confirmation == False
            # 无量突破应该是 weak 或 moderate
            assert result.signal_strength in ["weak", "moderate"]

    def test_scan_no_base_no_breakout(self, scanner):
        """测试无底部时不检测突破."""
        df = pd.DataFrame({
            'date': pd.date_range(start='2024-01-01', periods=30),
            'open': [100] * 30,
            'high': [105] * 30,
            'low': [95] * 30,
            'close': [100] * 30,
            'volume': [1000000] * 30,
        })
        
        base = IPOBase(ticker="TEST", has_base=False, base_type="unknown")
        result = scanner.scan(df, base)
        
        assert result.breakout_detected is False

    def test_scan_pullback_entry(self, scanner, base_info):
        """测试回测入场检测."""
        # 创建回测数据：突破后回到突破位附近
        dates = pd.date_range(start='2024-01-01', periods=60)
        
        # 前期上涨
        early = np.linspace(100, 115, 20)
        
        # 突破
        breakout = [122, 123, 124]
        
        # 回测到突破位附近
        pullback = [119.5, 120.2, 119.8]  # 在120±3%范围内
        
        # 企稳
        stabilize = [120.5, 121.0, 121.5]
        
        all_close = np.concatenate([early, breakout, pullback, stabilize])
        all_close = all_close[:len(dates)]
        
        df = pd.DataFrame({
            'date': dates[:len(all_close)],
            'open': all_close - 0.5,
            'high': all_close + 1,
            'low': all_close - 1,
            'close': all_close,
            'volume': [1000000] * len(all_close),
        })
        
        result = scanner.scan(df, base_info)
        
        # 应该检测到回测入场机会
        assert result.pullback_entry is True or result.breakout_detected is True

    def test_find_breakout(self, scanner):
        """测试突破日查找."""
        df = pd.DataFrame({
            'close': [100, 102, 105, 108, 115, 118, 120],  # 115突破110
        })
        
        idx = scanner._find_breakout(df, left_high=110)
        
        # 应该在索引4（价格115）突破
        assert idx == 4

    def test_find_breakout_none(self, scanner):
        """测试无突破情况."""
        df = pd.DataFrame({
            'close': [100, 102, 105, 108, 109, 108, 107],  # 从未突破120
        })
        
        idx = scanner._find_breakout(df, left_high=120)
        
        assert idx is None

    def test_calculate_strength(self, scanner, base_info):
        """测试信号强度计算."""
        breakout_row = pd.Series({
            'close': 125,
            'volume': 2500000,
            'rel_volume': 2.5,
            'rsi': 60,
        })
        
        strength = scanner._calculate_strength(
            breakout_row,
            volume_confirm=True,
            rsi_ok=True,
            base_info=base_info
        )
        
        assert strength in ["strong", "moderate", "weak"]

    def test_suggest_stop_loss(self, scanner, base_info):
        """测试止损位建议."""
        df = pd.DataFrame({
            'date': pd.date_range(start='2024-01-01', periods=50),
            'low': np.linspace(100, 120, 50),
        })
        
        stop = scanner._suggest_stop_loss(df, base_info, breakout_price=125)
        
        assert stop is not None
        assert stop < 125  # 止损应低于突破价

    def test_calculate_rs_rating(self, scanner):
        """测试RS评级计算."""
        df = pd.DataFrame({
            'close': np.linspace(100, 150, 50),  # 50%涨幅
        })
        
        rs = scanner._calculate_rs_rating(df, breakout_idx=45)
        
        assert rs is not None
        assert 0 <= rs <= 100


class TestBreakoutSignal:
    """测试BreakoutSignal数据类."""

    def test_signal_creation(self):
        """测试创建信号."""
        signal = BreakoutSignal(
            ticker="TEST",
            breakout_detected=True,
            breakout_date=date(2024, 3, 15),
            breakout_price=125.0,
            volume_confirmation=True,
            rs_rating=85.0,
            signal_strength="strong",
            suggested_stop=115.0,
            pullback_entry=False,
        )
        
        assert signal.ticker == "TEST"
        assert signal.breakout_detected is True
        assert signal.signal_strength == "strong"
        assert signal.volume_confirmation is True

    def test_signal_no_breakout(self):
        """测试无突破信号."""
        signal = BreakoutSignal(
            ticker="TEST",
            breakout_detected=False,
        )
        
        assert signal.breakout_detected is False
        assert signal.breakout_price is None


class TestPatternRecognizer:
    """测试形态识别器."""

    @pytest.fixture
    def recognizer(self):
        """创建识别器实例."""
        return PatternRecognizer()

    def test_analyze_structure(self, recognizer):
        """测试分析结果结构."""
        # 创建测试数据
        dates = pd.date_range(start='2024-01-01', periods=100)
        np.random.seed(42)
        close = 100 + np.random.randn(100).cumsum()
        
        df = pd.DataFrame({
            'date': dates,
            'open': close - 0.5,
            'high': close + 1,
            'low': close - 1,
            'close': close,
            'volume': np.random.randint(1000000, 5000000, 100),
        })
        
        result = recognizer.analyze(df, date(2024, 1, 1))
        
        assert "base" in result
        assert "breakout" in result
        assert "has_signal" in result
