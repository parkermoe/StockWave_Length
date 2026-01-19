"""
Trailing Stop Calculator

Computes dynamic trailing stop levels based on ATR and volatility regime.
The key insight: stops should "breathe" with the stock's volatility.
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional, Literal
from datetime import datetime

# Ensure parent directory is in path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class TrailingStopResult:
    """Container for trailing stop calculation results."""
    ticker: str
    current_price: float
    recent_high: float
    recent_high_date: datetime
    atr: float
    atr_period: int
    multiplier: float
    stop_level: float
    stop_distance: float  # Absolute distance from current price
    stop_distance_pct: float  # Percentage distance
    risk_per_share: float  # Dollar risk if stopped out from current price
    
    def __str__(self) -> str:
        return (
            f"Trailing Stop for {self.ticker}:\n"
            f"  Current Price: ${self.current_price:.2f}\n"
            f"  Recent High: ${self.recent_high:.2f} ({self.recent_high_date.strftime('%Y-%m-%d')})\n"
            f"  ATR({self.atr_period}): ${self.atr:.2f}\n"
            f"  Multiplier: {self.multiplier:.1f}x\n"
            f"  Stop Level: ${self.stop_level:.2f}\n"
            f"  Distance: ${self.stop_distance:.2f} ({self.stop_distance_pct:.1f}%)"
        )


def find_recent_high(
    df: pd.DataFrame,
    lookback_days: Optional[int] = None,
    entry_date: Optional[datetime] = None
) -> tuple[float, datetime]:
    """
    Find the recent high for trailing stop anchor.
    
    Args:
        df: DataFrame with 'High' column
        lookback_days: If provided, look back this many days from end
        entry_date: If provided, find high since this date
        
    Returns:
        Tuple of (high_price, high_date)
    """
    if entry_date is not None:
        # Find high since entry
        mask = df.index >= pd.Timestamp(entry_date)
        subset = df.loc[mask]
    elif lookback_days is not None:
        # Fixed lookback window
        subset = df.iloc[-lookback_days:]
    else:
        # Use all data (not recommended for trailing stops)
        subset = df
    
    if subset.empty:
        raise ValueError("No data in specified range for finding recent high")
    
    high_idx = subset['High'].idxmax()
    high_price = subset.loc[high_idx, 'High']
    
    return float(high_price), pd.Timestamp(high_idx).to_pydatetime()


def compute_trailing_stop(
    current_price: float,
    recent_high: float,
    recent_high_date: datetime,
    atr: float,
    multiplier: float = 2.0,
    ticker: str = "UNKNOWN",
    atr_period: int = 14
) -> TrailingStopResult:
    """
    Compute trailing stop level.
    
    The stop is placed at: recent_high - (multiplier * ATR)
    
    Args:
        current_price: Current stock price
        recent_high: Recent high price (anchor for trailing stop)
        recent_high_date: Date of the recent high
        atr: Current ATR value
        multiplier: ATR multiplier (e.g., 2.0 = 2x ATR below high)
        ticker: Stock symbol (for output)
        atr_period: ATR period used (for output)
        
    Returns:
        TrailingStopResult with stop level and related metrics
    """
    # Calculate stop level
    stop_distance_from_high = multiplier * atr
    stop_level = recent_high - stop_distance_from_high
    
    # Calculate distances from current price
    stop_distance = current_price - stop_level
    stop_distance_pct = (stop_distance / current_price) * 100 if current_price > 0 else 0
    
    # Risk per share (if you entered now and got stopped out)
    risk_per_share = stop_distance
    
    return TrailingStopResult(
        ticker=ticker,
        current_price=current_price,
        recent_high=recent_high,
        recent_high_date=recent_high_date,
        atr=atr,
        atr_period=atr_period,
        multiplier=multiplier,
        stop_level=stop_level,
        stop_distance=stop_distance,
        stop_distance_pct=stop_distance_pct,
        risk_per_share=risk_per_share
    )


def compute_chandelier_exit(
    df: pd.DataFrame,
    atr_period: int = 22,
    multiplier: float = 3.0,
    lookback: int = 22
) -> pd.Series:
    """
    Compute Chandelier Exit (a specific trailing stop indicator).
    
    Chandelier Exit = N-period High - (multiplier * ATR)
    
    Originally developed by Charles Le Beau.
    Default uses 22 periods and 3x ATR (more conservative than typical trailing stops).
    
    Args:
        df: DataFrame with OHLC data
        atr_period: Period for ATR calculation
        multiplier: ATR multiplier
        lookback: Lookback period for highest high
        
    Returns:
        Series of Chandelier Exit levels
    """
    from .atr import compute_atr
    
    atr_result = compute_atr(df, period=atr_period)
    highest_high = df['High'].rolling(window=lookback).max()
    
    chandelier = highest_high - (multiplier * atr_result.atr_series)
    chandelier.name = f'Chandelier_{lookback}_{multiplier}'
    
    return chandelier


def compute_keltner_stop(
    df: pd.DataFrame,
    ema_period: int = 20,
    atr_period: int = 10,
    multiplier: float = 2.0
) -> pd.Series:
    """
    Compute Keltner Channel lower band as a stop level.
    
    Keltner Lower = EMA - (multiplier * ATR)
    
    This is a mean-reversion style stop (reverts to moving average).
    
    Args:
        df: DataFrame with OHLC data
        ema_period: Period for center EMA
        atr_period: Period for ATR calculation
        multiplier: ATR multiplier for channel width
        
    Returns:
        Series of Keltner lower band levels
    """
    from .atr import compute_atr
    
    ema = df['Close'].ewm(span=ema_period, adjust=False).mean()
    atr_result = compute_atr(df, period=atr_period)
    
    keltner_lower = ema - (multiplier * atr_result.atr_series)
    keltner_lower.name = f'Keltner_Lower_{ema_period}_{multiplier}'
    
    return keltner_lower
