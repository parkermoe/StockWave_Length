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
class ScreenerConfig:
    """Stock screener parameters."""
    universe: str = "sp500"  # 'sp500', 'nasdaq100', or 'custom'
    min_price: float = 5.0  # Minimum stock price
    min_volume: int = 500_000  # Minimum average volume
    cache_ttl_hours: int = 24  # Cache TTL for fundamental data
    max_concurrent_requests: int = 5  # Max parallel API requests
    
    # Strategy-specific settings
    canslim_min_eps_growth: float = 25.0  # CANSLIM minimum EPS growth %
    canslim_min_rs_rating: float = 70.0  # CANSLIM minimum RS rating
    
    minervini_min_rs_rating: float = 70.0  # Minervini minimum RS rating
    minervini_max_atr_pct: float = 20.0  # Minervini max ATR% for consolidation
    
    volatility_min_atr_pct: float = 5.0  # High volatility min ATR%
    volatility_min_beta: float = 1.2  # High volatility min beta


@dataclass
class AnalystScoringConfig:
    """Analyst data scoring parameters."""
    enabled: bool = True  # Enable analyst multiplier adjustment
    weight_upside: float = 0.35  # Weight for price target upside
    weight_sentiment: float = 0.30  # Weight for analyst recommendations
    weight_momentum: float = 0.20  # Weight for recent upgrades/downgrades
    weight_coverage: float = 0.15  # Weight for analyst coverage depth
    min_multiplier: float = 0.8  # Minimum score multiplier
    max_multiplier: float = 1.2  # Maximum score multiplier
    min_analyst_count: int = 3  # Minimum analysts required for adjustment


@dataclass
class Config:
    """Main configuration container."""
    atr: ATRConfig = field(default_factory=ATRConfig)
    volatility_regime: VolatilityRegimeConfig = field(default_factory=VolatilityRegimeConfig)
    trailing_stop: TrailingStopConfig = field(default_factory=TrailingStopConfig)
    screener: ScreenerConfig = field(default_factory=ScreenerConfig)
    analyst_scoring: AnalystScoringConfig = field(default_factory=AnalystScoringConfig)
    
    # Data settings
    default_data_period: str = "1y"  # How much historical data to fetch
    
    # Default watchlist (can be overridden)
    watchlist: List[str] = field(default_factory=lambda: [
        "NVDA", "TSLA", "AAPL", "AMD", "META"
    ])


# Global default config instance
DEFAULT_CONFIG = Config()
