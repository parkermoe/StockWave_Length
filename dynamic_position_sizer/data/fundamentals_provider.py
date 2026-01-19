"""
Fundamental data provider for fetching company fundamentals and metrics.

Fetches fundamental data from yfinance and calculates derived metrics
like relative strength, price vs 52-week high, etc.
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.provider import DataProvider, DataProviderError
from data.yfinance_provider import YFinanceProvider
from data.cache_manager import get_cache


@dataclass
class FundamentalData:
    """Container for fundamental and derived metrics."""
    ticker: str
    
    # Price metrics
    current_price: float
    price_52w_high: float
    price_52w_low: float
    price_pct_from_52w_high: float  # Negative if below high
    price_pct_from_52w_low: float   # Positive if above low
    
    # Volume metrics
    avg_volume_10d: float
    avg_volume_50d: float
    volume_today: float
    volume_surge_ratio: float  # today / 50d avg
    
    # Moving averages
    ma_50: Optional[float] = None
    ma_150: Optional[float] = None
    ma_200: Optional[float] = None
    price_vs_ma_50: Optional[float] = None  # % above/below
    price_vs_ma_150: Optional[float] = None
    price_vs_ma_200: Optional[float] = None
    ma_50_above_ma_150: bool = False
    ma_50_above_ma_200: bool = False
    ma_150_above_ma_200: bool = False
    
    # Fundamental metrics (from yfinance info)
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    peg_ratio: Optional[float] = None
    
    # Growth metrics
    earnings_growth_qtrly: Optional[float] = None  # Quarterly YoY
    earnings_growth_annual: Optional[float] = None  # Annual
    revenue_growth_qtrly: Optional[float] = None
    revenue_growth_annual: Optional[float] = None
    
    # Profitability
    profit_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    roe: Optional[float] = None  # Return on equity
    
    # Institutional
    institutional_ownership: Optional[float] = None  # % of shares
    
    # Relative strength (vs SPY)
    rs_rating: Optional[float] = None  # 0-100 scale
    price_momentum_3m: Optional[float] = None  # % change
    price_momentum_6m: Optional[float] = None
    
    # Volatility
    atr_14: Optional[float] = None
    beta: Optional[float] = None
    
    # Analyst data
    analyst_target_mean: Optional[float] = None
    analyst_target_low: Optional[float] = None
    analyst_target_high: Optional[float] = None
    analyst_target_upside_pct: Optional[float] = None  # (target - price) / price * 100
    analyst_recommendation_mean: Optional[float] = None  # 1-5 scale (1=Strong Buy, 5=Sell)
    analyst_count: Optional[int] = None  # Number of analysts covering
    recent_upgrades_30d: int = 0  # Count of upgrades in last 30 days
    recent_downgrades_30d: int = 0  # Count of downgrades in last 30 days
    
    # Metadata
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap_category: Optional[str] = None  # 'mega', 'large', 'mid', 'small', 'micro'
    fetched_at: str = None
    
    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.now().isoformat()
        # Auto-classify market cap if not set
        if self.market_cap_category is None and self.market_cap:
            self.market_cap_category = self._classify_market_cap(self.market_cap)
    
    @staticmethod
    def _classify_market_cap(market_cap: float) -> str:
        """Classify market cap into categories.
        
        Categories:
        - Mega: $200B+
        - Large: $10B - $200B
        - Mid: $2B - $10B
        - Small: $300M - $2B
        - Micro: < $300M
        """
        if market_cap >= 200_000_000_000:
            return 'mega'
        elif market_cap >= 10_000_000_000:
            return 'large'
        elif market_cap >= 2_000_000_000:
            return 'mid'
        elif market_cap >= 300_000_000:
            return 'small'
        else:
            return 'micro'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for caching."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FundamentalData':
        """Create from dictionary."""
        return cls(**data)


class FundamentalsProvider:
    """
    Provider for fetching and calculating fundamental data.
    
    Uses yfinance for raw data and implements caching to reduce API calls.
    """
    
    def __init__(self, data_provider: Optional[DataProvider] = None, use_cache: bool = True):
        """
        Initialize the fundamentals provider.
        
        Args:
            data_provider: Data provider for OHLCV data (defaults to YFinance)
            use_cache: Whether to use caching (default True)
        """
        self.data_provider = data_provider or YFinanceProvider()
        self.use_cache = use_cache
        self.cache = get_cache() if use_cache else None
        
        # Cache SPY data for RS calculations
        self._spy_data = None
        self._spy_data_date = None
    
    def get_fundamentals(
        self,
        ticker: str,
        period: str = "1y",
        force_refresh: bool = False
    ) -> Optional[FundamentalData]:
        """
        Get fundamental data for a ticker.
        
        Args:
            ticker: Stock symbol
            period: Historical period for technical calculations
            force_refresh: Force refresh even if cached
            
        Returns:
            FundamentalData object or None if error
        """
        # Check cache first
        cache_key = f"fundamentals:{ticker}"
        if self.use_cache and not force_refresh:
            cached = self.cache.get(cache_key)
            if cached:
                return FundamentalData.from_dict(cached)
        
        try:
            # Fetch OHLCV data
            df = self.data_provider.get_ohlcv(ticker, period=period)
            if df.empty:
                return None
            
            # Get ticker info for fundamentals
            import yfinance as yf
            yf_ticker = yf.Ticker(ticker)
            info = yf_ticker.info
            
            # Calculate price metrics
            current_price = float(df['Close'].iloc[-1])
            high_52w = float(df['High'].max())
            low_52w = float(df['Low'].min())
            
            price_pct_from_high = ((current_price / high_52w) - 1) * 100
            price_pct_from_low = ((current_price / low_52w) - 1) * 100
            
            # Volume metrics
            volumes = df['Volume']
            avg_vol_10d = float(volumes.tail(10).mean())
            avg_vol_50d = float(volumes.tail(50).mean()) if len(volumes) >= 50 else avg_vol_10d
            volume_today = float(volumes.iloc[-1])
            volume_surge = volume_today / avg_vol_50d if avg_vol_50d > 0 else 1.0
            
            # Moving averages
            ma_50 = float(df['Close'].tail(50).mean()) if len(df) >= 50 else None
            ma_150 = float(df['Close'].tail(150).mean()) if len(df) >= 150 else None
            ma_200 = float(df['Close'].tail(200).mean()) if len(df) >= 200 else None
            
            price_vs_ma_50 = ((current_price / ma_50) - 1) * 100 if ma_50 else None
            price_vs_ma_150 = ((current_price / ma_150) - 1) * 100 if ma_150 else None
            price_vs_ma_200 = ((current_price / ma_200) - 1) * 100 if ma_200 else None
            
            ma_50_above_ma_150 = (ma_50 > ma_150) if (ma_50 and ma_150) else False
            ma_50_above_ma_200 = (ma_50 > ma_200) if (ma_50 and ma_200) else False
            ma_150_above_ma_200 = (ma_150 > ma_200) if (ma_150 and ma_200) else False
            
            # Calculate momentum
            price_3m_ago = df['Close'].iloc[-63] if len(df) >= 63 else df['Close'].iloc[0]
            price_6m_ago = df['Close'].iloc[-126] if len(df) >= 126 else df['Close'].iloc[0]
            momentum_3m = ((current_price / price_3m_ago) - 1) * 100
            momentum_6m = ((current_price / price_6m_ago) - 1) * 100
            
            # Calculate RS rating (relative strength vs SPY)
            rs_rating = self._calculate_rs_rating(ticker, df)
            
            # Calculate ATR
            from indicators import compute_atr
            atr_result = compute_atr(df, period=14)
            atr_14 = atr_result.current_atr
            
            # Fetch analyst data
            analyst_data = self._fetch_analyst_data(yf_ticker, current_price)
            
            # Extract info fields safely
            def safe_get(key, default=None):
                val = info.get(key, default)
                return val if val not in [None, 'N/A', float('inf'), float('-inf')] else default
            
            # Build FundamentalData object
            fundamental_data = FundamentalData(
                ticker=ticker,
                current_price=current_price,
                price_52w_high=high_52w,
                price_52w_low=low_52w,
                price_pct_from_52w_high=price_pct_from_high,
                price_pct_from_52w_low=price_pct_from_low,
                avg_volume_10d=avg_vol_10d,
                avg_volume_50d=avg_vol_50d,
                volume_today=volume_today,
                volume_surge_ratio=volume_surge,
                ma_50=ma_50,
                ma_150=ma_150,
                ma_200=ma_200,
                price_vs_ma_50=price_vs_ma_50,
                price_vs_ma_150=price_vs_ma_150,
                price_vs_ma_200=price_vs_ma_200,
                ma_50_above_ma_150=ma_50_above_ma_150,
                ma_50_above_ma_200=ma_50_above_ma_200,
                ma_150_above_ma_200=ma_150_above_ma_200,
                market_cap=safe_get('marketCap'),
                pe_ratio=safe_get('trailingPE'),
                forward_pe=safe_get('forwardPE'),
                peg_ratio=safe_get('pegRatio'),
                earnings_growth_qtrly=safe_get('earningsQuarterlyGrowth'),
                earnings_growth_annual=safe_get('earningsGrowth'),
                revenue_growth_qtrly=safe_get('revenueQuarterlyGrowth'),
                revenue_growth_annual=safe_get('revenueGrowth'),
                profit_margin=safe_get('profitMargins'),
                operating_margin=safe_get('operatingMargins'),
                roe=safe_get('returnOnEquity'),
                institutional_ownership=safe_get('heldPercentInstitutions'),
                rs_rating=rs_rating,
                price_momentum_3m=momentum_3m,
                price_momentum_6m=momentum_6m,
                atr_14=atr_14,
                beta=safe_get('beta'),
                analyst_target_mean=analyst_data.get('target_mean'),
                analyst_target_low=analyst_data.get('target_low'),
                analyst_target_high=analyst_data.get('target_high'),
                analyst_target_upside_pct=analyst_data.get('upside_pct'),
                analyst_recommendation_mean=analyst_data.get('recommendation_mean'),
                analyst_count=analyst_data.get('analyst_count'),
                recent_upgrades_30d=analyst_data.get('upgrades_30d', 0),
                recent_downgrades_30d=analyst_data.get('downgrades_30d', 0),
                sector=safe_get('sector'),
                industry=safe_get('industry')
            )
            
            # Cache the result
            if self.use_cache:
                self.cache.set(cache_key, fundamental_data.to_dict(), ttl=24)
            
            return fundamental_data
            
        except Exception as e:
            print(f"Error fetching fundamentals for {ticker}: {e}")
            return None
    
    def _calculate_rs_rating(self, ticker: str, df: pd.DataFrame) -> Optional[float]:
        """
        Calculate relative strength rating (0-100) vs SPY.
        
        Higher is better. 90+ means outperforming 90% of the time.
        """
        try:
            # Get SPY data (cached)
            spy_df = self._get_spy_data()
            if spy_df is None:
                return None
            
            # Align dates
            common_dates = df.index.intersection(spy_df.index)
            if len(common_dates) < 63:  # Need at least 3 months
                return None
            
            ticker_returns = df.loc[common_dates, 'Close'].pct_change()
            spy_returns = spy_df.loc[common_dates, 'Close'].pct_change()
            
            # Calculate rolling outperformance
            outperformance = ticker_returns > spy_returns
            rs_rating = (outperformance.sum() / len(outperformance)) * 100
            
            return float(rs_rating)
            
        except Exception:
            return None
    
    def _get_spy_data(self) -> Optional[pd.DataFrame]:
        """Get SPY data with caching (refreshed daily)."""
        today = datetime.now().date()
        
        if self._spy_data is not None and self._spy_data_date == today:
            return self._spy_data
        
        try:
            self._spy_data = self.data_provider.get_ohlcv('SPY', period='1y')
            self._spy_data_date = today
            return self._spy_data
        except Exception:
            return None
    
    def _fetch_analyst_data(self, yf_ticker, current_price: float) -> Dict[str, Any]:
        """
        Fetch analyst data from yfinance ticker object.
        
        Args:
            yf_ticker: yfinance Ticker object
            current_price: Current stock price for upside calculation
            
        Returns:
            Dictionary with analyst metrics
        """
        analyst_data = {
            'target_mean': None,
            'target_low': None,
            'target_high': None,
            'upside_pct': None,
            'recommendation_mean': None,
            'analyst_count': None,
            'upgrades_30d': 0,
            'downgrades_30d': 0
        }
        
        try:
            info = yf_ticker.info
            
            # Get price targets from info
            target_mean = info.get('targetMeanPrice')
            target_low = info.get('targetLowPrice')
            target_high = info.get('targetHighPrice')
            
            if target_mean and target_mean > 0:
                analyst_data['target_mean'] = float(target_mean)
                analyst_data['upside_pct'] = ((target_mean - current_price) / current_price) * 100
            
            if target_low and target_low > 0:
                analyst_data['target_low'] = float(target_low)
            
            if target_high and target_high > 0:
                analyst_data['target_high'] = float(target_high)
            
            # Get recommendation mean (1-5 scale: 1=Strong Buy, 5=Sell)
            rec_mean = info.get('recommendationMean')
            if rec_mean:
                analyst_data['recommendation_mean'] = float(rec_mean)
            
            # Get analyst count
            analyst_count = info.get('numberOfAnalystOpinions')
            if analyst_count:
                analyst_data['analyst_count'] = int(analyst_count)
            
            # Get upgrades/downgrades from last 30 days
            try:
                upgrades_downgrades = yf_ticker.upgrades_downgrades
                if upgrades_downgrades is not None and not upgrades_downgrades.empty:
                    # Filter to last 30 days
                    thirty_days_ago = datetime.now() - timedelta(days=30)
                    recent = upgrades_downgrades[upgrades_downgrades.index >= thirty_days_ago]
                    
                    if not recent.empty and 'action' in recent.columns:
                        # Count upgrades and downgrades
                        analyst_data['upgrades_30d'] = len(recent[recent['action'].str.lower().str.contains('up', na=False)])
                        analyst_data['downgrades_30d'] = len(recent[recent['action'].str.lower().str.contains('down', na=False)])
            except Exception:
                # If upgrades_downgrades fails, continue with zeros
                pass
                
        except Exception as e:
            # If any error fetching analyst data, return empty dict
            print(f"Warning: Could not fetch analyst data: {e}")
        
        return analyst_data

