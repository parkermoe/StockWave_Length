"""
Average True Range (ATR) calculation.

ATR measures market volatility by decomposing the entire range of an asset price
for a given period. It was originally developed for commodities but has become
widely used for stocks and other instruments.

True Range is the greatest of:
- Current High minus Current Low
- Absolute value of Current High minus Previous Close
- Absolute value of Current Low minus Previous Close

ATR is then a moving average of the True Range.
"""
import pandas as pd
import numpy as np
from typing import Literal
from dataclasses import dataclass


@dataclass
class ATRResult:
    """Container for ATR calculation results."""
    atr_series: pd.Series  # Full ATR series
    current_atr: float     # Most recent ATR value
    period: int            # ATR period used
    method: str            # Calculation method used


def compute_true_range(df: pd.DataFrame) -> pd.Series:
    """
    Compute True Range for each period.
    
    True Range = max(
        High - Low,
        abs(High - Previous Close),
        abs(Low - Previous Close)
    )
    
    Args:
        df: DataFrame with 'High', 'Low', 'Close' columns
        
    Returns:
        Series of True Range values
    """
    high = df['High']
    low = df['Low']
    close = df['Close']
    prev_close = close.shift(1)
    
    # Three components of True Range
    hl = high - low
    hpc = (high - prev_close).abs()
    lpc = (low - prev_close).abs()
    
    # True Range is the maximum of the three
    true_range = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
    true_range.name = 'TrueRange'
    
    return true_range


def compute_atr_wilder(true_range: pd.Series, period: int = 14) -> pd.Series:
    """
    Compute ATR using Wilder's smoothing method.
    
    Wilder's smoothing is equivalent to an EMA with alpha = 1/period,
    but with a specific initialization (SMA for first value).
    
    This is the original/traditional method.
    
    Args:
        true_range: Series of True Range values
        period: Smoothing period (default 14)
        
    Returns:
        Series of ATR values
    """
    atr = pd.Series(index=true_range.index, dtype=float)
    
    # First ATR value is simple average of first `period` true ranges
    first_atr_idx = period - 1
    if len(true_range) < period:
        return atr  # Not enough data
    
    atr.iloc[first_atr_idx] = true_range.iloc[:period].mean()
    
    # Subsequent values use Wilder's smoothing
    # ATR_t = ((period - 1) * ATR_{t-1} + TR_t) / period
    multiplier = (period - 1) / period
    
    for i in range(period, len(true_range)):
        atr.iloc[i] = (multiplier * atr.iloc[i-1]) + (true_range.iloc[i] / period)
    
    atr.name = f'ATR_{period}_wilder'
    return atr


def compute_atr_sma(true_range: pd.Series, period: int = 14) -> pd.Series:
    """
    Compute ATR using Simple Moving Average.
    
    This is a simpler alternative to Wilder's method.
    More responsive to recent changes but noisier.
    
    Args:
        true_range: Series of True Range values
        period: SMA period (default 14)
        
    Returns:
        Series of ATR values
    """
    atr = true_range.rolling(window=period).mean()
    atr.name = f'ATR_{period}_sma'
    return atr


def compute_atr_ema(true_range: pd.Series, period: int = 14) -> pd.Series:
    """
    Compute ATR using Exponential Moving Average.
    
    A middle ground between Wilder's smoothing and SMA.
    
    Args:
        true_range: Series of True Range values  
        period: EMA period (default 14)
        
    Returns:
        Series of ATR values
    """
    atr = true_range.ewm(span=period, adjust=False).mean()
    atr.name = f'ATR_{period}_ema'
    return atr


def compute_atr(
    df: pd.DataFrame, 
    period: int = 14, 
    method: Literal["wilder", "sma", "ema"] = "wilder"
) -> ATRResult:
    """
    Compute Average True Range for price data.
    
    Args:
        df: DataFrame with 'High', 'Low', 'Close' columns
        period: ATR period (default 14)
        method: Calculation method - "wilder" (default), "sma", or "ema"
        
    Returns:
        ATRResult with full series and current value
        
    Raises:
        ValueError: If invalid method specified or insufficient data
    """
    if len(df) < period + 1:
        raise ValueError(
            f"Insufficient data: need at least {period + 1} rows, got {len(df)}"
        )
    
    # Compute True Range
    true_range = compute_true_range(df)
    
    # Compute ATR based on method
    method = method.lower()
    if method == "wilder":
        atr_series = compute_atr_wilder(true_range, period)
    elif method == "sma":
        atr_series = compute_atr_sma(true_range, period)
    elif method == "ema":
        atr_series = compute_atr_ema(true_range, period)
    else:
        raise ValueError(f"Unknown ATR method: {method}. Use 'wilder', 'sma', or 'ema'.")
    
    # Get current (most recent) ATR value
    current_atr = atr_series.dropna().iloc[-1] if not atr_series.dropna().empty else np.nan
    
    return ATRResult(
        atr_series=atr_series,
        current_atr=float(current_atr),
        period=period,
        method=method
    )


def compute_atr_multiple_periods(
    df: pd.DataFrame,
    periods: list[int] = [7, 14, 21],
    method: str = "wilder"
) -> dict[int, ATRResult]:
    """
    Compute ATR for multiple periods at once.
    
    Useful for comparing volatility across different timeframes.
    
    Args:
        df: DataFrame with OHLC data
        periods: List of ATR periods to compute
        method: Calculation method
        
    Returns:
        Dictionary mapping period -> ATRResult
    """
    results = {}
    for period in periods:
        try:
            results[period] = compute_atr(df, period, method)
        except ValueError:
            continue  # Skip if insufficient data for this period
    return results
