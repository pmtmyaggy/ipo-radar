"""突破扫描器 - 检测IPO底部突破信号.

检测突破信号和回测入场机会。
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd
import numpy as np

from .indicators import relative_volume, rsi
from .ipo_base_detector import IPOBase, IPOBaseDetector

logger = logging.getLogger(__name__)


@dataclass
class BreakoutSignal:
    """突破信号."""
    ticker: str
    breakout_detected: bool
    breakout_date: Optional[date] = None
    breakout_price: Optional[float] = None
    volume_confirmation: bool = False  # 成交量 > 1.5x 均量
    rs_rating: Optional[float] = None  # 相对强度 0-100
    signal_strength: str = "weak"  # strong, moderate, weak
    suggested_stop: Optional[float] = None  # 建议止损位
    pullback_entry: bool = False  # 是否回测入场机会


class BreakoutScanner:
    """突破扫描器.
    
    检测突破信号：价格突破左侧高点 + 成交量确认。
    """
    
    # 突破确认条件
    VOLUME_THRESHOLD = 1.5  # 成交量需大于1.5倍平均
    RSI_MIN = 50  # RSI最小值
    RSI_MAX = 70  # RSI最大值（不超买）
    
    def __init__(self):
        """初始化扫描器."""
        self.logger = logging.getLogger(__name__)
    
    def scan(self, df: pd.DataFrame, base_info: IPOBase) -> BreakoutSignal:
        """检测突破信号.
        
        突破确认条件:
        - 收盘价 > 左侧高点
        - 当日成交量 > 20日均量的1.5倍
        - RSI在50-70之间(不超买)
        
        另外检测'回测入场'信号：
        - 突破后回踩突破位并企稳
        
        Args:
            df: OHLCV DataFrame
            base_info: 底部形态信息
        
        Returns:
            BreakoutSignal检测结果
        """
        if not base_info.has_base or not base_info.left_high:
            return BreakoutSignal(ticker=base_info.ticker, breakout_detected=False)
        
        ticker = base_info.ticker
        left_high = base_info.left_high
        
        try:
            # 确保数据足够
            if len(df) < 20:
                return BreakoutSignal(ticker=ticker, breakout_detected=False)
            
            # 计算指标
            df = df.copy()
            df['rsi'] = rsi(df['close'])
            df['rel_volume'] = relative_volume(df['volume'])
            
            # 检查是否有突破
            breakout_idx = self._find_breakout(df, left_high)
            
            if breakout_idx is None:
                # 检查是否有回测入场机会
                pullback = self._check_pullback(df, left_high)
                
                return BreakoutSignal(
                    ticker=ticker,
                    breakout_detected=False,
                    pullback_entry=pullback,
                )
            
            # 获取突破日数据
            breakout_row = df.iloc[breakout_idx]
            breakout_date = breakout_row['date']
            breakout_price = breakout_row['close']
            
            # 检查成交量确认
            volume_confirm = breakout_row['rel_volume'] >= self.VOLUME_THRESHOLD
            
            # 检查RSI
            rsi_value = breakout_row['rsi']
            rsi_ok = self.RSI_MIN <= rsi_value <= self.RSI_MAX
            
            # 计算信号强度
            strength = self._calculate_strength(
                breakout_row, volume_confirm, rsi_ok, base_info
            )
            
            # 计算RS评级
            rs_rating = self._calculate_rs_rating(df, breakout_idx)
            
            # 建议止损位
            stop_loss = self._suggest_stop_loss(df, base_info, breakout_price)
            
            return BreakoutSignal(
                ticker=ticker,
                breakout_detected=True,
                breakout_date=breakout_date if isinstance(breakout_date, date) else breakout_date.date(),
                breakout_price=round(breakout_price, 2),
                volume_confirmation=volume_confirm,
                rs_rating=round(rs_rating, 1) if rs_rating else None,
                signal_strength=strength,
                suggested_stop=round(stop_loss, 2) if stop_loss else None,
                pullback_entry=False,
            )
            
        except Exception as e:
            self.logger.error(f"Error scanning breakout for {ticker}: {e}")
            return BreakoutSignal(ticker=ticker, breakout_detected=False)
    
    def _find_breakout(self, df: pd.DataFrame, left_high: float) -> Optional[int]:
        """找到突破日的索引.
        
        条件：收盘价 > 左侧高点
        """
        # 查找收盘价突破左侧高点的日期
        breakout_mask = df['close'] > left_high
        
        if not breakout_mask.any():
            return None
        
        # 获取第一个突破日
        breakout_indices = breakout_mask[breakout_mask].index
        
        if len(breakout_indices) == 0:
            return None
        
        # 返回相对位置
        return df.index.get_loc(breakout_indices[0])
    
    def _check_pullback(self, df: pd.DataFrame, left_high: float) -> bool:
        """检查是否有回测入场机会.
        
        条件：
        - 曾经突破过
        - 现在回踩到突破位附近（±3%）
        - 企稳（不再下跌）
        """
        try:
            # 获取最近10天数据
            recent = df.tail(10)
            
            if len(recent) < 5:
                return False
            
            # 检查最近收盘价是否在突破位附近
            current_price = recent['close'].iloc[-1]
            
            # 在突破位±3%范围内
            if abs(current_price - left_high) / left_high <= 0.03:
                # 检查是否企稳（最近3天不再创新低）
                last_3_lows = recent['low'].tail(3)
                if last_3_lows.is_monotonic_increasing:
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _calculate_strength(
        self,
        breakout_row: pd.Series,
        volume_confirm: bool,
        rsi_ok: bool,
        base_info: IPOBase,
    ) -> str:
        """计算信号强度."""
        score = 0
        
        # 成交量确认 +3
        if volume_confirm:
            score += 3
        
        # RSI合适 +2
        if rsi_ok:
            score += 2
        
        # 形态质量 +2
        if base_info.base_type in ["flat", "cup"]:
            score += 2
        
        # 紧密度 +2
        if base_info.tightness and base_info.tightness > 0.7:
            score += 2
        
        # 成交量萎缩 +1
        if base_info.volume_dry_up:
            score += 1
        
        # 根据分数判断强度
        if score >= 8:
            return "strong"
        elif score >= 5:
            return "moderate"
        else:
            return "weak"
    
    def _calculate_rs_rating(self, df: pd.DataFrame, breakout_idx: int) -> Optional[float]:
        """计算相对强度评级 (0-100).
        
        简化的RS计算：与IPO初期相比的价格强度
        """
        try:
            if breakout_idx < 5 or len(df) < 20:
                return None
            
            # IPO初期价格（前5天平均）
            ipo_price = df.head(5)['close'].mean()
            
            # 当前价格
            current_price = df.iloc[breakout_idx]['close']
            
            if ipo_price > 0:
                # 计算相对表现（相对于IPO的涨幅）
                performance = (current_price - ipo_price) / ipo_price
                
                # 转换为0-100的评级（假设-20%到+100%映射到0-100）
                rs = 50 + (performance * 100)
                return max(0, min(100, rs * 50))  # 归一化
            
            return None
            
        except Exception:
            return None
    
    def _suggest_stop_loss(
        self,
        df: pd.DataFrame,
        base_info: IPOBase,
        breakout_price: float,
    ) -> Optional[float]:
        """建议止损位.
        
        策略：设在底部低点下方5-8%
        """
        try:
            # 找到底部期间的最低点
            if base_info.base_start and base_info.base_end:
                base_low = df[
                    (df['date'] >= pd.Timestamp(base_info.base_start)) &
                    (df['date'] <= pd.Timestamp(base_info.base_end))
                ]['low'].min()
            else:
                # 使用左侧高点后的最低点
                base_low = df.tail(20)['low'].min()
            
            # 设在低点下方7%
            stop = base_low * 0.93
            
            # 确保止损不超过突破价的10%
            max_stop = breakout_price * 0.90
            
            return min(stop, max_stop)
            
        except Exception:
            return None


class PatternRecognizer:
    """形态识别器 - 整合检测和扫描."""
    
    def __init__(self):
        """初始化."""
        self.base_detector = IPOBaseDetector()
        self.breakout_scanner = BreakoutScanner()
    
    def analyze(self, df: pd.DataFrame, ipo_date: date) -> dict:
        """综合分析.
        
        Args:
            df: OHLCV DataFrame
            ipo_date: IPO日期
        
        Returns:
            分析结果字典
        """
        # 检测底部形态
        base = self.base_detector.detect(df, ipo_date)
        
        # 检测突破信号
        breakout = self.breakout_scanner.scan(df, base)
        
        return {
            "base": base,
            "breakout": breakout,
            "has_signal": breakout.breakout_detected or breakout.pullback_entry,
        }
