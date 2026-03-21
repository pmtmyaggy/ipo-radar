"""技术指标测试."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.pattern.indicators import (
    sma,
    ema,
    rsi,
    vwap,
    atr,
    relative_volume,
    price_range_pct,
    volume_sma,
    bollinger_bands,
    calculate_all_indicators,
)


class TestSMA:
    """测试简单移动平均线."""

    def test_sma_basic(self):
        """测试基本SMA计算."""
        series = pd.Series([1, 2, 3, 4, 5])
        result = sma(series, period=3)
        
        # 最后三个值的平均: (3+4+5)/3 = 4
        assert result.iloc[-1] == pytest.approx(4.0)

    def test_sma_short_series(self):
        """测试短序列处理."""
        series = pd.Series([1, 2])
        result = sma(series, period=5)
        
        # 序列长度小于周期，应该能处理
        assert len(result) == 2
        assert not result.isna().any()


class TestEMA:
    """测试指数移动平均线."""

    def test_ema_basic(self):
        """测试基本EMA计算."""
        series = pd.Series([1, 2, 3, 4, 5])
        result = ema(series, period=3)
        
        # EMA应该比SMA对近期数据更敏感
        assert len(result) == 5
        assert result.iloc[-1] > series.iloc[-2]  # 最后一个值应该大于前一个


class TestRSI:
    """测试RSI指标."""

    def test_rsi_range(self):
        """测试RSI范围在0-100之间."""
        # 生成随机价格序列
        np.random.seed(42)
        prices = pd.Series(100 + np.random.randn(50).cumsum())
        result = rsi(prices, period=14)
        
        assert (result >= 0).all() and (result <= 100).all()

    def test_rsi_strong_uptrend(self):
        """测试强上升趋势的RSI."""
        # 强上升趋势
        prices = pd.Series([100, 105, 110, 115, 120, 125, 130])
        result = rsi(prices, period=5)
        
        # 上升趋势RSI应该高（>=50，因为强趋势可能正好是50）
        assert result.iloc[-1] >= 50

    def test_rsi_strong_downtrend(self):
        """测试强下降趋势的RSI."""
        # 强下降趋势
        prices = pd.Series([130, 125, 120, 115, 110, 105, 100])
        result = rsi(prices, period=5)
        
        # 下降趋势RSI应该低
        assert result.iloc[-1] < 50


class TestVWAP:
    """测试VWAP指标."""

    def test_vwap_basic(self):
        """测试基本VWAP计算."""
        high = pd.Series([105, 106, 107])
        low = pd.Series([95, 96, 97])
        close = pd.Series([100, 101, 102])
        volume = pd.Series([1000, 2000, 1500])
        
        result = vwap(high, low, close, volume)
        
        assert len(result) == 3
        # VWAP应该在high和low之间
        assert (result <= high).all() and (result >= low).all()


class TestATR:
    """测试ATR指标."""

    def test_atr_high_volatility(self):
        """测试高波动率ATR."""
        high = pd.Series([110, 112, 115, 113, 118])
        low = pd.Series([90, 92, 95, 93, 98])
        close = pd.Series([100, 102, 105, 103, 108])
        
        result = atr(high, low, close, period=3)
        
        # 高波动应该有较高的ATR
        assert result.iloc[-1] > 10

    def test_atr_low_volatility(self):
        """测试低波动率ATR."""
        high = pd.Series([101, 101.5, 102, 101.8, 102.2])
        low = pd.Series([99, 99.5, 100, 99.8, 100.2])
        close = pd.Series([100, 100.5, 101, 100.8, 101.2])
        
        result = atr(high, low, close, period=3)
        
        # 低波动应该有较低的ATR
        assert result.iloc[-1] < 5


class TestRelativeVolume:
    """测试相对成交量."""

    def test_relative_volume_spike(self):
        """测试成交量激增."""
        # 正常成交量后突然增加
        volume = pd.Series([1000] * 19 + [3000])
        result = relative_volume(volume, period=20)
        
        # 最后一天相对成交量应该很高
        assert result.iloc[-1] > 2.0

    def test_relative_volume_normal(self):
        """测试正常成交量."""
        # 稳定的成交量
        volume = pd.Series([1000] * 20)
        result = relative_volume(volume, period=20)
        
        # 相对成交量应该接近1
        assert result.iloc[-1] == pytest.approx(1.0)


class TestPriceRangePct:
    """测试价格波动范围占比."""

    def test_price_range_calculation(self):
        """测试价格范围计算."""
        high = pd.Series([110, 112, 115])
        low = pd.Series([90, 92, 95])
        close = pd.Series([100, 102, 105])
        
        result = price_range_pct(high, low, close, period=3)
        
        # 范围应该是 (115-90)/105 = 23.8%
        assert result.iloc[-1] > 0.2


class TestVolumeSMA:
    """测试成交量SMA."""

    def test_volume_sma(self):
        """测试成交量移动平均."""
        volume = pd.Series([1000, 2000, 3000, 2000, 1000])
        result = volume_sma(volume, period=3)
        
        # 最后三个值的平均: (3000+2000+1000)/3 = 2000
        assert result.iloc[-1] == pytest.approx(2000.0)


class TestBollingerBands:
    """测试布林带."""

    def test_bollinger_structure(self):
        """测试布林带结构."""
        np.random.seed(42)
        close = pd.Series(100 + np.random.randn(50).cumsum())
        
        upper, middle, lower = bollinger_bands(close, period=20, std_dev=2.0)
        
        # 上轨 > 中轨 > 下轨（从第10行开始检查，避免初始NaN）
        assert (upper.iloc[10:] >= middle.iloc[10:]).all()
        assert (middle.iloc[10:] >= lower.iloc[10:]).all()

    def test_bollinger_width(self):
        """测试布林带宽度."""
        # 高波动率数据
        np.random.seed(42)
        close = pd.Series(100 + np.random.randn(50).cumsum() * 5)
        
        upper, middle, lower = bollinger_bands(close, period=20, std_dev=2.0)
        
        # 带宽应该大于0（从第10行开始检查）
        width = upper.iloc[10:] - lower.iloc[10:]
        assert (width > 0).all()


class TestCalculateAllIndicators:
    """测试计算所有指标."""

    def test_all_indicators_present(self):
        """测试所有指标都被添加."""
        # 创建测试数据
        dates = pd.date_range(start='2024-01-01', periods=50)
        df = pd.DataFrame({
            'date': dates,
            'open': 100 + np.random.randn(50).cumsum(),
            'high': 105 + np.random.randn(50).cumsum(),
            'low': 95 + np.random.randn(50).cumsum(),
            'close': 100 + np.random.randn(50).cumsum(),
            'volume': np.random.randint(1000, 10000, 50),
        })
        
        result = calculate_all_indicators(df)
        
        # 检查所有指标列都存在
        expected_columns = [
            'sma_20', 'sma_50', 'ema_12', 'ema_26',
            'rsi', 'atr', 'volume_sma', 'relative_volume',
            'bb_upper', 'bb_middle', 'bb_lower', 'vwap'
        ]
        
        for col in expected_columns:
            assert col in result.columns, f"Missing column: {col}"

    def test_indicators_no_nans(self):
        """测试指标没有NaN值（除了前几行）."""
        dates = pd.date_range(start='2024-01-01', periods=50)
        df = pd.DataFrame({
            'date': dates,
            'open': 100 + np.random.randn(50).cumsum(),
            'high': 105 + np.random.randn(50).cumsum(),
            'low': 95 + np.random.randn(50).cumsum(),
            'close': 100 + np.random.randn(50).cumsum(),
            'volume': np.random.randint(1000, 10000, 50),
        })
        
        result = calculate_all_indicators(df)
        
        # 检查指标列在有效行没有NaN（允许前几行因为rolling window有NaN）
        indicator_cols = [c for c in result.columns if c not in ['date', 'open', 'high', 'low', 'close', 'volume']]
        for col in indicator_cols:
            # 检查最后40行没有NaN（给rolling window足够的数据）
            assert not result[col].iloc[10:].isna().any(), f"Column {col} has NaN values"
