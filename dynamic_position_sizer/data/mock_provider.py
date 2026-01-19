"""
Mock data provider for testing and demonstration.

Generates realistic-looking price data without network access.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional

from data.provider import DataProvider


class MockDataProvider(DataProvider):
    """
    Mock data provider that generates synthetic price data.
    
    Useful for:
    - Testing without network access
    - Demonstrations
    - Unit tests
    
    The generated data mimics realistic stock behavior with:
    - Geometric Brownian Motion for price evolution
    - Volatility clustering (GARCH-like behavior)
    - Realistic OHLC relationships
    """
    
    # Preset characteristics for common tickers
    TICKER_PROFILES = {
        "NVDA": {"base_price": 140.0, "annual_vol": 0.55, "drift": 0.15},
        "TSLA": {"base_price": 250.0, "annual_vol": 0.60, "drift": 0.10},
        "AAPL": {"base_price": 195.0, "annual_vol": 0.25, "drift": 0.08},
        "AMD": {"base_price": 120.0, "annual_vol": 0.50, "drift": 0.12},
        "META": {"base_price": 520.0, "annual_vol": 0.40, "drift": 0.10},
        "MSFT": {"base_price": 420.0, "annual_vol": 0.22, "drift": 0.07},
        "GOOGL": {"base_price": 175.0, "annual_vol": 0.28, "drift": 0.08},
        "AMZN": {"base_price": 200.0, "annual_vol": 0.35, "drift": 0.09},
        "SPY": {"base_price": 590.0, "annual_vol": 0.15, "drift": 0.06},
        "QQQ": {"base_price": 510.0, "annual_vol": 0.20, "drift": 0.08},
    }
    
    DEFAULT_PROFILE = {"base_price": 100.0, "annual_vol": 0.30, "drift": 0.05}
    
    def __init__(self, seed: Optional[int] = None):
        """
        Initialize mock provider.
        
        Args:
            seed: Random seed for reproducibility
        """
        self.rng = np.random.default_rng(seed)
    
    def _get_profile(self, ticker: str) -> dict:
        """Get characteristics for a ticker."""
        return self.TICKER_PROFILES.get(ticker.upper(), self.DEFAULT_PROFILE)
    
    def _generate_ohlcv(
        self,
        days: int,
        base_price: float,
        annual_vol: float,
        drift: float
    ) -> pd.DataFrame:
        """
        Generate synthetic OHLCV data using geometric Brownian motion.
        """
        # Convert annual parameters to daily
        daily_vol = annual_vol / np.sqrt(252)
        daily_drift = drift / 252
        
        # Generate returns with volatility clustering
        vol_persistence = 0.9
        vol_shock = 0.3
        
        # Initial volatility state
        vol_state = daily_vol
        
        closes = [base_price]
        highs = [base_price * 1.01]
        lows = [base_price * 0.99]
        opens = [base_price]
        volumes = []
        
        for i in range(days - 1):
            # Update volatility state (simple GARCH-like)
            vol_state = vol_persistence * vol_state + \
                       (1 - vol_persistence) * daily_vol + \
                       vol_shock * daily_vol * abs(self.rng.standard_normal())
            
            # Generate return
            ret = daily_drift + vol_state * self.rng.standard_normal()
            
            # Generate OHLC
            prev_close = closes[-1]
            new_close = prev_close * (1 + ret)
            
            # Open near previous close with small gap
            gap = self.rng.uniform(-0.005, 0.005)
            new_open = prev_close * (1 + gap)
            
            # High and low based on intraday volatility
            intraday_range = vol_state * 1.5
            new_high = max(new_open, new_close) * (1 + abs(self.rng.standard_normal()) * intraday_range)
            new_low = min(new_open, new_close) * (1 - abs(self.rng.standard_normal()) * intraday_range)
            
            opens.append(new_open)
            highs.append(new_high)
            lows.append(new_low)
            closes.append(new_close)
            
            # Volume (higher on volatile days)
            base_volume = 10_000_000
            vol_multiplier = 1 + 2 * (vol_state / daily_vol - 1)
            volumes.append(int(base_volume * vol_multiplier * self.rng.uniform(0.5, 1.5)))
        
        # First day volume
        volumes.insert(0, int(10_000_000 * self.rng.uniform(0.5, 1.5)))
        
        # Create date index
        end_date = datetime.now()
        dates = pd.date_range(end=end_date, periods=days, freq='B')  # Business days
        
        df = pd.DataFrame({
            'Open': opens,
            'High': highs,
            'Low': lows,
            'Close': closes,
            'Volume': volumes
        }, index=dates)
        
        return df
    
    def get_ohlcv(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Generate synthetic OHLCV data for a ticker.
        
        Args:
            ticker: Stock symbol
            period: Time period (supports: 1mo, 3mo, 6mo, 1y, 2y)
            interval: Data interval (only 1d supported for mock)
            
        Returns:
            DataFrame with OHLCV data
        """
        # Parse period to days
        period_days = {
            "1mo": 21,
            "3mo": 63,
            "6mo": 126,
            "1y": 252,
            "2y": 504,
            "5y": 1260
        }
        days = period_days.get(period, 252)
        
        profile = self._get_profile(ticker)
        
        return self._generate_ohlcv(
            days=days,
            base_price=profile["base_price"],
            annual_vol=profile["annual_vol"],
            drift=profile["drift"]
        )
    
    def get_current_price(self, ticker: str) -> float:
        """Get the most recent (simulated) price."""
        df = self.get_ohlcv(ticker, period="1mo")
        return float(df['Close'].iloc[-1])


# Convenience function
def get_mock_data(ticker: str, period: str = "1y", seed: int = 42) -> pd.DataFrame:
    """Quick helper to get mock data."""
    provider = MockDataProvider(seed=seed)
    return provider.get_ohlcv(ticker, period)
