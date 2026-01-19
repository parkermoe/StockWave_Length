"""
Universe provider for fetching stock universes (S&P 500, NASDAQ-100, etc).

Provides lists of tickers to screen, with caching and filtering capabilities.
"""
import sys
from pathlib import Path
import pandas as pd
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.cache_manager import get_cache


class UniverseProvider(ABC):
    """Abstract base class for stock universe providers."""
    
    @abstractmethod
    def get_tickers(self, force_refresh: bool = False) -> List[str]:
        """Get list of tickers in this universe."""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the name of this universe."""
        pass


class SP500Provider(UniverseProvider):
    """
    S&P 500 universe provider.
    
    Fetches S&P 500 constituents from Wikipedia with caching.
    """
    
    def __init__(self, use_cache: bool = True):
        """
        Initialize S&P 500 provider.
        
        Args:
            use_cache: Whether to use caching (default True, 7-day TTL)
        """
        self.use_cache = use_cache
        self.cache = get_cache() if use_cache else None
    
    def get_name(self) -> str:
        return "S&P 500"
    
    def get_tickers(self, force_refresh: bool = False) -> List[str]:
        """
        Get S&P 500 tickers from Wikipedia.
        
        Args:
            force_refresh: Force refresh even if cached
            
        Returns:
            List of ticker symbols
        """
        cache_key = "universe:sp500"
        
        # Check cache first
        if self.use_cache and not force_refresh:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        
        try:
            # Fetch from Wikipedia
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            tables = pd.read_html(url)
            sp500_table = tables[0]
            tickers = sp500_table['Symbol'].tolist()
            
            # Clean tickers (some have special characters)
            tickers = [ticker.replace('.', '-') for ticker in tickers]
            
            # Cache for 7 days (S&P 500 doesn't change often)
            if self.use_cache:
                self.cache.set(cache_key, tickers, ttl=168)  # 7 days
            
            return tickers
            
        except Exception as e:
            print(f"Error fetching S&P 500 tickers: {e}")
            # Fallback to a static list of major components if fetch fails
            return self._get_fallback_tickers()
    
    def _get_fallback_tickers(self) -> List[str]:
        """Return a subset of major S&P 500 stocks as fallback."""
        return [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B', 'UNH', 'JNJ',
            'JPM', 'V', 'PG', 'XOM', 'HD', 'CVX', 'MA', 'BAC', 'ABBV', 'PFE',
            'COST', 'DIS', 'ADBE', 'CRM', 'CSCO', 'ACN', 'MRK', 'PEP', 'TMO', 'NFLX',
            'ABT', 'LIN', 'NKE', 'AVGO', 'CMCSA', 'WMT', 'DHR', 'TXN', 'AMD', 'QCOM',
            'NEE', 'PM', 'UPS', 'RTX', 'IBM', 'ORCL', 'HON', 'INTC', 'INTU', 'COP'
        ]


class NASDAQ100Provider(UniverseProvider):
    """
    NASDAQ-100 universe provider.
    
    Fetches NASDAQ-100 constituents from Wikipedia.
    """
    
    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self.cache = get_cache() if use_cache else None
    
    def get_name(self) -> str:
        return "NASDAQ-100"
    
    def get_tickers(self, force_refresh: bool = False) -> List[str]:
        """Get NASDAQ-100 tickers."""
        cache_key = "universe:nasdaq100"
        
        if self.use_cache and not force_refresh:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        
        try:
            url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
            tables = pd.read_html(url)
            nasdaq_table = tables[4]  # The component table is usually the 5th table
            tickers = nasdaq_table['Ticker'].tolist()
            
            # Clean tickers
            tickers = [ticker.replace('.', '-') for ticker in tickers]
            
            if self.use_cache:
                self.cache.set(cache_key, tickers, ttl=168)
            
            return tickers
            
        except Exception as e:
            print(f"Error fetching NASDAQ-100 tickers: {e}")
            return []


class CustomUniverseProvider(UniverseProvider):
    """
    Custom universe from a list or CSV file.
    """
    
    def __init__(self, tickers: Optional[List[str]] = None, csv_path: Optional[str] = None):
        """
        Initialize custom universe.
        
        Args:
            tickers: List of ticker symbols
            csv_path: Path to CSV file with 'ticker' or 'symbol' column
        """
        self.tickers_list = tickers
        self.csv_path = csv_path
    
    def get_name(self) -> str:
        return "Custom Universe"
    
    def get_tickers(self, force_refresh: bool = False) -> List[str]:
        """Get custom universe tickers."""
        if self.tickers_list:
            return self.tickers_list
        
        if self.csv_path:
            try:
                df = pd.read_csv(self.csv_path)
                # Try common column names
                for col in ['ticker', 'Ticker', 'symbol', 'Symbol', 'SYMBOL', 'TICKER']:
                    if col in df.columns:
                        return df[col].tolist()
            except Exception as e:
                print(f"Error reading CSV: {e}")
        
        return []


class Russell2000Provider(UniverseProvider):
    """
    Russell 2000 universe provider (small/mid cap stocks).
    
    Since Russell 2000 list isn't readily available from Wikipedia,
    we use a representative sample of small/mid cap stocks.
    """
    
    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self.cache = get_cache() if use_cache else None
    
    def get_name(self) -> str:
        return "Russell 2000"
    
    def get_tickers(self, force_refresh: bool = False) -> List[str]:
        """Get Russell 2000 representative tickers."""
        cache_key = "universe:russell2000"
        
        if self.use_cache and not force_refresh:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        
        # Representative small/mid cap stocks across sectors
        # In production, you'd fetch from a data provider or CSV
        tickers = [
            # Technology
            'SSNC', 'ZION', 'FHN', 'COHR', 'CIEN', 'LITE', 'QLYS', 'CYBR', 'COMM', 'SLAB',
            # Healthcare
            'CORT', 'LMAT', 'HOLX', 'NEOG', 'XRAY', 'ICUI', 'GMED', 'ALGN', 'INSP', 'ENSG',
            # Financials
            'UMBF', 'BOKF', 'WTFC', 'SFNC', 'PBCT', 'IBOC', 'BANR', 'UCBI', 'CCBG', 'FBNC',
            # Industrials
            'AIT', 'WERN', 'GWR', 'JBHT', 'ATKR', 'UFPI', 'TREX', 'AZEK', 'CMCO', 'ALG',
            # Consumer
            'TXRH', 'PLNT', 'JACK', 'SHAK', 'WING', 'CHUY', 'BLMN', 'DENN', 'CAKE', 'PLAY',
            # Materials
            'SLGN', 'BECN', 'RMBS', 'ARCH', 'CEIX', 'AMR', 'USLM', 'HCC', 'IOSP', 'MTX',
            # Energy
            'RRC', 'CIVI', 'VNOM', 'REI', 'TALO', 'ESTE', 'NEXT', 'MGY', 'PR', 'CRGY',
            # Real Estate
            'REXR', 'CUBE', 'ELS', 'COLD', 'SUI', 'TRNO', 'SAFE', 'EPRT', 'GTY', 'FCPT'
        ]
        
        if self.use_cache:
            self.cache.set(cache_key, tickers, ttl=168)  # 7 days
        
        return tickers


class AllMarketsProvider(UniverseProvider):
    """
    Combined universe: S&P 500 + Russell 2000 (all market caps).
    """
    
    def __init__(self, use_cache: bool = True):
        self.sp500 = SP500Provider(use_cache=use_cache)
        self.russell2000 = Russell2000Provider(use_cache=use_cache)
    
    def get_name(self) -> str:
        return "All Markets (S&P 500 + Russell 2000)"
    
    def get_tickers(self, force_refresh: bool = False) -> List[str]:
        """Get combined universe."""
        sp500_tickers = set(self.sp500.get_tickers(force_refresh))
        russell_tickers = set(self.russell2000.get_tickers(force_refresh))
        
        # Combine and remove duplicates
        all_tickers = sorted(sp500_tickers.union(russell_tickers))
        return all_tickers


class UniverseFilter:
    """
    Filter universe by liquidity, market cap, sector, and other criteria.
    """
    
    def __init__(
        self,
        min_price: float = 5.0,
        min_volume: int = 500_000,
        min_market_cap: Optional[float] = None,
        max_market_cap: Optional[float] = None,
        cap_categories: Optional[List[str]] = None,  # ['mega', 'large', 'mid', 'small', 'micro']
        sectors: Optional[List[str]] = None,  # Include only these sectors
        exclude_sectors: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,  # Include only these industries
        exclude_industries: Optional[List[str]] = None
    ):
        """
        Initialize universe filter.
        
        Args:
            min_price: Minimum price per share (default $5)
            min_volume: Minimum average daily volume (default 500k)
            min_market_cap: Minimum market cap in dollars (optional)
            max_market_cap: Maximum market cap in dollars (optional)
            cap_categories: List of cap categories to include (optional)
            sectors: List of sectors to include (optional, mutually exclusive with exclude_sectors)
            exclude_sectors: List of sectors to exclude (optional)
            industries: List of industries to include (optional)
            exclude_industries: List of industries to exclude (optional)
        """
        self.min_price = min_price
        self.min_volume = min_volume
        self.min_market_cap = min_market_cap
        self.max_market_cap = max_market_cap
        self.cap_categories = cap_categories
        self.sectors = sectors
        self.exclude_sectors = exclude_sectors or []
        self.industries = industries
        self.exclude_industries = exclude_industries or []
    
    def filter_tickers(
        self,
        tickers: List[str],
        fundamental_data: Dict[str, Any]
    ) -> List[str]:
        """
        Filter tickers based on criteria.
        
        Args:
            tickers: List of tickers to filter
            fundamental_data: Dict mapping ticker -> FundamentalData
            
        Returns:
            Filtered list of tickers
        """
        filtered = []
        
        for ticker in tickers:
            data = fundamental_data.get(ticker)
            if not data:
                continue
            
            # Price filter
            if data.current_price < self.min_price:
                continue
            
            # Volume filter
            if data.avg_volume_50d < self.min_volume:
                continue
            
            # Market cap filters
            if data.market_cap:
                if self.min_market_cap and data.market_cap < self.min_market_cap:
                    continue
                if self.max_market_cap and data.market_cap > self.max_market_cap:
                    continue
            
            # Market cap category filter
            if self.cap_categories and data.market_cap_category:
                if data.market_cap_category not in self.cap_categories:
                    continue
            
            # Sector filters (include takes precedence over exclude)
            if self.sectors:
                if data.sector not in self.sectors:
                    continue
            elif data.sector in self.exclude_sectors:
                continue
            
            # Industry filters (include takes precedence over exclude)
            if self.industries:
                if data.industry not in self.industries:
                    continue
            elif data.industry in self.exclude_industries:
                continue
            
            filtered.append(ticker)
        
        return filtered


def get_universe(name: str = "sp500", **kwargs) -> UniverseProvider:
    """
    Factory function to get a universe provider.
    
    Args:
        name: Universe name ('sp500', 'nasdaq100', 'russell2000', 'all', 'custom')
        **kwargs: Additional arguments for the provider
        
    Returns:
        UniverseProvider instance
    """
    providers = {
        'sp500': SP500Provider,
        's&p500': SP500Provider,
        'nasdaq100': NASDAQ100Provider,
        'nasdaq': NASDAQ100Provider,
        'russell2000': Russell2000Provider,
        'russell': Russell2000Provider,
        'all': AllMarketsProvider,
        'all_markets': AllMarketsProvider,
        'custom': CustomUniverseProvider
    }
    
    provider_class = providers.get(name.lower())
    if not provider_class:
        raise ValueError(f"Unknown universe: {name}. Available: {list(providers.keys())}")
    
    return provider_class(**kwargs)
