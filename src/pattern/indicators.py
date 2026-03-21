"""技术指标计算 - 纯函数集合.

计算各种技术分析指标，全部使用pandas实现。
"""

import pandas as pd
import numpy as np
from typing import Optional


def sma(series: pd.Series, period: int) -> pd.Series:
    """简单移动平均线.
    
    Args:
        series: 价格序列
        period: 周期
    
    Returns:
        SMA序列
    """
    return series.rolling(window=period, min_periods=1).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """指数移动平均线.
    
    Args:
        series: 价格序列
        period: 周期
    
    Returns:
        EMA序列
    """
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """相对强弱指标 (RSI).
    
    Args:
        series: 价格序列
        period: 周期，默认14
    
    Returns:
        RSI序列 (0-100)
    """
    delta = series.diff()
    
    # 分离上涨和下跌
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # 计算平均上涨和下跌
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    
    # 计算RS和RSI
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    return rsi.fillna(50)  # 填充NaN为中性值


def vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
) -> pd.Series:
    """成交量加权平均价 (VWAP).
    
    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        volume: 成交量序列
    
    Returns:
        VWAP序列
    """
    typical_price = (high + low + close) / 3
    vwap = (typical_price * volume).cumsum() / volume.cumsum()
    return vwap


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """平均真实波幅 (ATR).
    
    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        period: 周期，默认14
    
    Returns:
        ATR序列
    """
    # 计算真实波幅
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # 计算ATR
    atr = tr.rolling(window=period, min_periods=1).mean()
    
    return atr


def relative_volume(volume: pd.Series, period: int = 20) -> pd.Series:
    """相对成交量.
    
    当前成交量 / 过去N天平均成交量
    
    Args:
        volume: 成交量序列
        period: 周期，默认20
    
    Returns:
        相对成交量序列
    """
    avg_volume = volume.rolling(window=period, min_periods=1).mean()
    return volume / avg_volume.replace(0, np.nan)


def price_range_pct(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 20,
) -> pd.Series:
    """过去N天的价格波动范围占比.
    
    (High - Low) / Close
    
    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        period: 周期，默认20
    
    Returns:
        波动范围占比序列
    """
    range_high = high.rolling(window=period, min_periods=1).max()
    range_low = low.rolling(window=period, min_periods=1).min()
    
    price_range = range_high - range_low
    avg_close = close.rolling(window=period, min_periods=1).mean()
    
    return price_range / avg_close.replace(0, np.nan)


def volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    """成交量简单移动平均.
    
    Args:
        volume: 成交量序列
        period: 周期
    
    Returns:
        成交量SMA
    """
    return volume.rolling(window=period, min_periods=1).mean()


def bollinger_bands(
    close: pd.Series,
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """布林带.
    
    Args:
        close: 收盘价序列
        period: 周期，默认20
        std_dev: 标准差倍数，默认2.0
    
    Returns:
        (上轨, 中轨, 下轨)
    """
    middle = sma(close, period)
    std = close.rolling(window=period, min_periods=1).std()
    
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    
    return upper, middle, lower


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算所有技术指标.
    
    Args:
        df: 包含OHLCV的DataFrame
    
    Returns:
        添加了指标的DataFrame
    """
    df = df.copy()
    
    # 移动平均线
    df['sma_20'] = sma(df['close'], 20)
    df['sma_50'] = sma(df['close'], 50)
    df['ema_12'] = ema(df['close'], 12)
    df['ema_26'] = ema(df['close'], 26)
    
    # 动量指标
    df['rsi'] = rsi(df['close'], 14)
    
    # 波动率
    df['atr'] = atr(df['high'], df['low'], df['close'], 14)
    
    # 成交量
    df['volume_sma'] = volume_sma(df['volume'], 20)
    df['relative_volume'] = relative_volume(df['volume'], 20)
    
    # 布林带
    df['bb_upper'], df['bb_middle'], df['bb_lower'] = bollinger_bands(df['close'], 20, 2.0)
    
    # VWAP（按天计算需要分组，这里简化）
    df['vwap'] = vwap(df['high'], df['low'], df['close'], df['volume'])
    
    return df
