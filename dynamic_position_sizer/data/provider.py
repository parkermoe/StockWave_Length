"""
Abstract base class for data providers.
"""
from abc import ABC, abstractmethod
import pandas as pd


class DataProvider(ABC):
    """
    Abstract interface for market data providers.
    
    All data providers must implement get_ohlcv() which returns
    a DataFrame with standardized columns.
    """
    
    @abstractmethod
    def get_ohlcv(
        self, 
        ticker: str, 
        period: str = "1y",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for a given ticker.
        
        Args:
            ticker: Stock symbol (e.g., "NVDA", "AAPL")
            period: How far back to fetch (e.g., "6mo", "1y", "2y")
            interval: Data interval (e.g., "1d", "1h")
            
        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
            Index should be DatetimeIndex
            
        Raises:
            DataProviderError: If data cannot be fetched
        """
        pass
    
    @abstractmethod
    def get_current_price(self, ticker: str) -> float:
        """
        Get the most recent price for a ticker.
        
        Args:
            ticker: Stock symbol
            
        Returns:
            Most recent closing price (or last traded price)
        """
        pass


class DataProviderError(Exception):
    """Raised when data provider encounters an error."""
    pass
