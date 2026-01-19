"""
Volatility Regime Detection

Classifies whether a stock is currently in a low, normal, elevated, or extreme
volatility regime relative to its own historical volatility.

This is crucial for dynamic stop-loss adjustment:
- Low vol regime: Can use tighter stops (less noise)
- High vol regime: Need wider stops (more noise to filter)
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Literal, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from indicators.atr import compute_atr, ATRResult


@dataclass
class VolatilityRegime:
    """Container for volatility regime analysis."""
    current_atr: float
    historical_mean: float
    historical_std: float
    percentile: float  # 0-100, where current ATR falls in historical distribution
    regime: Literal["low", "normal", "elevated", "extreme"]
    z_score: float  # Standard deviations from mean
    
    def __str__(self) -> str:
        return (
            f"Volatility Regime: {self.regime.upper()} "
            f"(ATR: ${self.current_atr:.2f}, {self.percentile:.0f}th percentile)"
        )


def classify_regime(
    percentile: float,
    thresholds: Optional[dict] = None
) -> Literal["low", "normal", "elevated", "extreme"]:
    """
    Classify volatility regime based on percentile.
    
    Args:
        percentile: Current ATR percentile (0-100)
        thresholds: Custom thresholds dict, or None for defaults
        
    Returns:
        Regime classification string
    """
    if thresholds is None:
        thresholds = {
            "low": 25,
            "normal": 75,
            "elevated": 90,
            "extreme": 100
        }
    
    if percentile <= thresholds["low"]:
        return "low"
    elif percentile <= thresholds["normal"]:
        return "normal"
    elif percentile <= thresholds["elevated"]:
        return "elevated"
    else:
        return "extreme"


def compute_volatility_regime(
    df: pd.DataFrame,
    atr_period: int = 14,
    lookback_days: int = 252,
    thresholds: Optional[dict] = None
) -> VolatilityRegime:
    """
    Analyze the current volatility regime for a stock.
    
    Computes ATR, then compares current ATR to its historical distribution
    to determine if we're in a low, normal, elevated, or extreme vol environment.
    
    Args:
        df: DataFrame with OHLC data (should have at least lookback_days of data)
        atr_period: Period for ATR calculation (default 14)
        lookback_days: Days of history to use for regime classification (default 252 = 1 year)
        thresholds: Custom percentile thresholds for regime classification
        
    Returns:
        VolatilityRegime with classification and statistics
    """
    # Compute ATR
    atr_result = compute_atr(df, period=atr_period, method="wilder")
    atr_series = atr_result.atr_series.dropna()
    
    if len(atr_series) < lookback_days:
        # Use whatever history we have
        lookback_days = len(atr_series)
    
    # Get historical ATR values for percentile calculation
    historical_atr = atr_series.iloc[-lookback_days:]
    current_atr = atr_series.iloc[-1]
    
    # Compute statistics
    historical_mean = historical_atr.mean()
    historical_std = historical_atr.std()
    
    # Percentile: what % of historical values are below current?
    percentile = (historical_atr < current_atr).sum() / len(historical_atr) * 100
    
    # Z-score: how many standard deviations from mean?
    z_score = (current_atr - historical_mean) / historical_std if historical_std > 0 else 0
    
    # Classify regime
    regime = classify_regime(percentile, thresholds)
    
    return VolatilityRegime(
        current_atr=float(current_atr),
        historical_mean=float(historical_mean),
        historical_std=float(historical_std),
        percentile=float(percentile),
        regime=regime,
        z_score=float(z_score)
    )


def compute_rolling_regime(
    df: pd.DataFrame,
    atr_period: int = 14,
    lookback_days: int = 252
) -> pd.DataFrame:
    """
    Compute rolling volatility regime classification.
    
    Returns a DataFrame with regime classification at each point in time.
    Useful for backtesting or visualization.
    
    Args:
        df: DataFrame with OHLC data
        atr_period: ATR calculation period
        lookback_days: Rolling window for percentile calculation
        
    Returns:
        DataFrame with columns: ATR, Percentile, Regime
    """
    atr_result = compute_atr(df, period=atr_period)
    atr_series = atr_result.atr_series
    
    # Rolling percentile
    def rolling_percentile(series, window):
        """Compute rolling percentile rank."""
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            window_data = series.iloc[i-window:i]
            current = series.iloc[i]
            pct = (window_data < current).sum() / window * 100
            result.iloc[i] = pct
        return result
    
    percentile_series = rolling_percentile(atr_series.dropna(), lookback_days)
    
    # Classify each point
    regime_series = percentile_series.apply(classify_regime)
    
    result_df = pd.DataFrame({
        'ATR': atr_series,
        'Percentile': percentile_series,
        'Regime': regime_series
    })
    
    return result_df


def get_regime_multiplier(
    regime: VolatilityRegime,
    base_multiplier: float = 2.0,
    adjustments: Optional[dict] = None
) -> float:
    """
    Get the recommended ATR multiplier based on volatility regime.
    
    Args:
        regime: VolatilityRegime object
        base_multiplier: Default multiplier (used for 'normal' regime)
        adjustments: Dict mapping regime -> multiplier, or None for defaults
        
    Returns:
        Recommended ATR multiplier for stop-loss calculation
    """
    if adjustments is None:
        adjustments = {
            "low": 1.5,
            "normal": 2.0,
            "elevated": 2.5,
            "extreme": 3.0
        }
    
    return adjustments.get(regime.regime, base_multiplier)
