"""
Configuration and default parameters for the dynamic position sizer.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class ATRConfig:
    """ATR calculation parameters."""
    default_period: int = 14
    method: str = "wilder"  # "wilder" or "sma"


@dataclass
class VolatilityRegimeConfig:
    """Volatility regime classification parameters."""
    lookback_days: int = 252  # 1 year of trading days
    thresholds: dict = field(default_factory=lambda: {
        "low": 25,        # Below 25th percentile
        "normal": 75,     # 25th - 75th percentile
        "elevated": 90,   # 75th - 90th percentile
        "extreme": 100    # Above 90th percentile
    })


@dataclass
class TrailingStopConfig:
    """Trailing stop calculation parameters."""
    base_multiplier: float = 2.0
    regime_adjustments: dict = field(default_factory=lambda: {
        "low": 1.5,
        "normal": 2.0,
        "elevated": 2.5,
        "extreme": 3.0
    })
    recent_high_lookback: int = 20  # Days to look back for recent high (if no entry provided)


@dataclass
class Config:
    """Main configuration container."""
    atr: ATRConfig = field(default_factory=ATRConfig)
    volatility_regime: VolatilityRegimeConfig = field(default_factory=VolatilityRegimeConfig)
    trailing_stop: TrailingStopConfig = field(default_factory=TrailingStopConfig)
    
    # Data settings
    default_data_period: str = "1y"  # How much historical data to fetch
    
    # Default watchlist (can be overridden)
    watchlist: List[str] = field(default_factory=lambda: [
        "NVDA", "TSLA", "AAPL", "AMD", "META"
    ])


# Global default config instance
DEFAULT_CONFIG = Config()
