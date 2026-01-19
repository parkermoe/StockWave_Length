"""
Yahoo Finance data provider implementation using yfinance.
"""
import sys
from pathlib import Path
import pandas as pd
import yfinance as yf
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.provider import DataProvider, DataProviderError


class YFinanceProvider(DataProvider):
    """
    Data provider using Yahoo Finance via yfinance library.
    
    This is the default provider - free, no API key required,
    good for daily OHLCV data on US equities.
    
    Note: yfinance is unofficial and can occasionally break.
    For production use, consider a paid provider.
    """
    
    def __init__(self, cache_enabled: bool = True):
        """
        Initialize the YFinance provider.
        
        Args:
            cache_enabled: Whether to cache ticker objects (reduces API calls)
        """
        self.cache_enabled = cache_enabled
        self._ticker_cache: dict = {}
    
    def _get_ticker(self, symbol: str) -> yf.Ticker:
        """Get or create a Ticker object, with optional caching."""
        if self.cache_enabled and symbol in self._ticker_cache:
            return self._ticker_cache[symbol]
        
        ticker = yf.Ticker(symbol)
        
        if self.cache_enabled:
            self._ticker_cache[symbol] = ticker
        
        return ticker
    
    def get_ohlcv(
        self, 
        ticker: str, 
        period: str = "1y",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from Yahoo Finance.
        
        Args:
            ticker: Stock symbol (e.g., "NVDA")
            period: Valid periods: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
            interval: Valid intervals: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo
            
        Returns:
            DataFrame with OHLCV data, datetime-indexed
            
        Raises:
            DataProviderError: If ticker not found or data unavailable
        """
        try:
            yf_ticker = self._get_ticker(ticker)
            df = yf_ticker.history(period=period, interval=interval)
            
            if df.empty:
                raise DataProviderError(
                    f"No data returned for ticker '{ticker}'. "
                    "Check if the symbol is valid."
                )
            
            # Standardize column names (yfinance already uses these, but ensure consistency)
            expected_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            
            # yfinance includes 'Dividends' and 'Stock Splits' - drop them
            df = df[expected_cols].copy()
            
            # Ensure index is DatetimeIndex
            df.index = pd.to_datetime(df.index)
            
            # Remove timezone info for consistency
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            
            return df
            
        except DataProviderError:
            raise
        except Exception as e:
            raise DataProviderError(
                f"Failed to fetch data for '{ticker}': {str(e)}"
            )
    
    def get_current_price(self, ticker: str) -> float:
        """
        Get the most recent price for a ticker.
        
        Uses the last closing price from daily data.
        For intraday, this might be slightly delayed.
        
        Args:
            ticker: Stock symbol
            
        Returns:
            Most recent closing price
        """
        try:
            df = self.get_ohlcv(ticker, period="5d", interval="1d")
            return float(df['Close'].iloc[-1])
        except Exception as e:
            raise DataProviderError(
                f"Failed to get current price for '{ticker}': {str(e)}"
            )
    
    def get_ticker_info(self, ticker: str) -> Optional[dict]:
        """
        Get additional ticker information (company name, sector, etc.)
        
        Args:
            ticker: Stock symbol
            
        Returns:
            Dictionary with ticker info, or None if unavailable
        """
        try:
            yf_ticker = self._get_ticker(ticker)
            return yf_ticker.info
        except Exception:
            return None


# Convenience function for quick data access
def fetch_ohlcv(ticker: str, period: str = "1y") -> pd.DataFrame:
    """
    Quick helper to fetch OHLCV data.
    
    Usage:
        df = fetch_ohlcv("NVDA", "6mo")
    """
    provider = YFinanceProvider()
    return provider.get_ohlcv(ticker, period)
