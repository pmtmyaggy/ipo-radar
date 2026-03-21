"""IPO底部形态检测器.

识别IPO后的底部形态：平底、杯型、三角形等。
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import numpy as np

from .indicators import sma, volume_sma, price_range_pct

logger = logging.getLogger(__name__)


@dataclass
class IPOBase:
    """IPO底部形态."""
    ticker: str
    has_base: bool
    base_type: str  # flat, cup, ascending_triangle, descending_triangle, unknown
    base_start: Optional[date] = None
    base_end: Optional[date] = None
    base_depth_pct: Optional[float] = None  # 从左侧高点回撤%
    base_length_days: Optional[int] = None
    left_high: Optional[float] = None  # 突破目标价
    tightness: Optional[float] = None  # 末期波动收窄程度 0-1
    volume_dry_up: bool = False  # 盘整期量能萎缩


class IPOBaseDetector:
    """IPO底部形态检测器.
    
    识别IPO后的底部形态，基于William O'Neil的CANSLIM方法。
    """
    
    # 形态识别参数
    MIN_BASE_DAYS = 14  # 最小底部时间（2周）
    MAX_BASE_DAYS = 84  # 最大底部时间（12周）
    MIN_DEPTH_PCT = 0.10  # 最小回撤10%
    MAX_DEPTH_PCT = 0.50  # 最大回撤50%
    
    def __init__(self):
        """初始化检测器."""
        self.logger = logging.getLogger(__name__)
    
    def detect(self, df: pd.DataFrame, ipo_date: date) -> IPOBase:
        """检测IPO后的底部形态.
        
        识别逻辑:
        1. 找到IPO后的第一个显著高点(左侧高点)
        2. 之后的回调是否在10-50%范围内
        3. 是否形成了可识别的底部形态
        4. 底部末期波动是否收窄
        5. 底部时间是否在2-12周范围内
        
        Args:
            df: OHLCV DataFrame，必须包含date, open, high, low, close, volume
            ipo_date: IPO上市日期
        
        Returns:
            IPOBase检测结果
        """
        if df.empty:
            return IPOBase(ticker="", has_base=False, base_type="unknown")
        
        ticker = df.get('ticker', [''])[0] if 'ticker' in df.columns else ""
        
        # 确保日期列是datetime
        df = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'])
        
        # 过滤IPO后的数据
        df = df[df['date'] >= pd.Timestamp(ipo_date)]
        
        if len(df) < self.MIN_BASE_DAYS:
            return IPOBase(ticker=ticker, has_base=False, base_type="unknown")
        
        try:
            # 找到左侧高点
            left_high_idx, left_high_price = self._find_left_high(df)
            
            if left_high_idx is None or left_high_idx < 5:
                return IPOBase(ticker=ticker, has_base=False, base_type="unknown")
            
            # 获取底部区域数据（左侧高点之后）
            base_df = df.iloc[left_high_idx:].copy()
            
            if len(base_df) < self.MIN_BASE_DAYS:
                return IPOBase(ticker=ticker, has_base=False, base_type="unknown")
            
            # 计算底部深度
            base_low = base_df['low'].min()
            base_depth = (left_high_price - base_low) / left_high_price
            
            # 检查深度是否在范围内
            if not (self.MIN_DEPTH_PCT <= base_depth <= self.MAX_DEPTH_PCT):
                return IPOBase(ticker=ticker, has_base=False, base_type="unknown")
            
            # 计算底部时间
            base_length = len(base_df)
            
            # 计算底部类型
            base_type = self._classify_base_type(base_df, left_high_price, base_low)
            
            # 计算紧密度（末期波动收窄程度）
            tightness = self._calculate_tightness(base_df)
            
            # 检查成交量萎缩
            volume_dry_up = self._check_volume_dry_up(df, base_df)
            
            # 构建结果
            base = IPOBase(
                ticker=ticker,
                has_base=True,
                base_type=base_type,
                base_start=base_df['date'].iloc[0].date(),
                base_end=base_df['date'].iloc[-1].date() if base_length >= self.MIN_BASE_DAYS else None,
                base_depth_pct=round(base_depth * 100, 2),
                base_length_days=base_length,
                left_high=round(left_high_price, 2),
                tightness=round(tightness, 2) if tightness else None,
                volume_dry_up=volume_dry_up,
            )
            
            return base
            
        except Exception as e:
            self.logger.error(f"Error detecting base for {ticker}: {e}")
            return IPOBase(ticker=ticker, has_base=False, base_type="unknown")
    
    def _find_left_high(self, df: pd.DataFrame) -> tuple:
        """找到左侧高点（IPO后的第一个显著高点）.
        
        策略：找到前N天内的最高点，且该高点比IPO开盘价高至少10%
        """
        if len(df) < 10:
            return None, None
        
        ipo_price = df['open'].iloc[0]
        
        # 在前30天内找最高点
        lookback = min(30, len(df))
        early_data = df.iloc[:lookback]
        
        high_idx = early_data['high'].idxmax()
        high_price = early_data.loc[high_idx, 'high']
        
        # 确保比IPO价高10%以上
        if high_price >= ipo_price * 1.10:
            # 转换为相对于DataFrame起始位置的索引
            relative_idx = df.index.get_loc(high_idx)
            return relative_idx, high_price
        
        return None, None
    
    def _classify_base_type(
        self,
        base_df: pd.DataFrame,
        left_high: float,
        base_low: float,
    ) -> str:
        """分类底部形态类型."""
        # 平底：深度 < 15%，价格区间狭窄
        depth = (left_high - base_low) / left_high
        if depth < 0.15:
            return "flat"
        
        # 杯型：深度15-35%，U型底部
        if 0.15 <= depth <= 0.35:
            # 检查是否为U型（右侧高于左侧）
            first_half = base_df.iloc[:len(base_df)//2]
            second_half = base_df.iloc[len(base_df)//2:]
            
            if second_half['close'].mean() > first_half['close'].mean():
                return "cup"
        
        # 上升三角形：低点抬高，高点平稳
        lows = base_df['low'].values
        highs = base_df['high'].values
        
        # 简单检查：低点上升趋势，高点平稳
        low_trend = np.polyfit(range(len(lows)), lows, 1)[0]
        high_trend = np.polyfit(range(len(highs)), highs, 1)[0]
        
        if low_trend > 0 and abs(high_trend) < 0.01:
            return "ascending_triangle"
        
        # 下降三角形：高点下降，低点平稳
        if high_trend < 0 and abs(low_trend) < 0.01:
            return "descending_triangle"
        
        return "unknown"
    
    def _calculate_tightness(self, base_df: pd.DataFrame) -> Optional[float]:
        """计算底部末期波动收窄程度.
        
        越接近1表示波动越窄（越好）
        
        计算方法：末期5天ATR / 整个底部ATR
        """
        if len(base_df) < 10:
            return None
        
        try:
            # 计算整个底部的平均波动
            full_range = (base_df['high'] - base_df['low']).mean()
            
            # 计算末期5天的平均波动
            last_5 = base_df.tail(5)
            last_range = (last_5['high'] - last_5['low']).mean()
            
            if full_range > 0:
                tightness = 1 - (last_range / full_range)
                return max(0, min(1, tightness))  # 限制在0-1范围内
            
            return None
            
        except Exception:
            return None
    
    def _check_volume_dry_up(
        self,
        full_df: pd.DataFrame,
        base_df: pd.DataFrame,
    ) -> bool:
        """检查盘整期成交量是否萎缩.
        
        比较底部期间成交量 vs IPO初期成交量
        """
        try:
            # IPO初期成交量（前10天）
            ipo_volume = full_df.head(10)['volume'].mean()
            
            # 底部期间成交量
            base_volume = base_df['volume'].mean()
            
            if ipo_volume > 0:
                ratio = base_volume / ipo_volume
                return ratio < 0.7  # 萎缩30%以上
            
            return False
            
        except Exception:
            return False
