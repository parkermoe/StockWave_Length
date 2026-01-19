"""
Stop Loss Recommender

The main orchestrator that pulls everything together:
- Fetches data
- Computes ATR
- Analyzes volatility regime
- Generates stop-loss recommendations
"""
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

import sys
from pathlib import Path

# Add parent directory to path for direct script execution
sys.path.insert(0, str(Path(__file__).parent.parent))

from data import YFinanceProvider, DataProviderError
from indicators import (
    compute_atr, 
    compute_volatility_regime, 
    get_regime_multiplier,
    VolatilityRegime
)
from position.trailing_stop import (
    find_recent_high,
    compute_trailing_stop,
    TrailingStopResult
)
from config import DEFAULT_CONFIG


@dataclass
class StopRecommendation:
    """Complete stop-loss recommendation with all context."""
    
    # Core recommendation
    ticker: str
    current_price: float
    suggested_stop: float
    stop_distance_pct: float
    
    # ATR details
    atr_14: float
    atr_7: Optional[float] = None
    atr_21: Optional[float] = None
    
    # Multiplier details
    base_multiplier: float = 2.0
    regime_adjusted_multiplier: float = 2.0
    
    # Volatility regime
    volatility_regime: Optional[VolatilityRegime] = None
    
    # High/anchor details
    recent_high: float = 0.0
    recent_high_date: Optional[datetime] = None
    
    # Entry-specific (if provided)
    entry_price: Optional[float] = None
    initial_stop: Optional[float] = None
    
    # Position sizing helpers
    risk_per_share: float = 0.0
    
    # Metadata
    generated_at: datetime = field(default_factory=datetime.now)
    data_period: str = "1y"
    
    def shares_for_risk(self, risk_dollars: float) -> int:
        """Calculate position size for a given dollar risk."""
        if self.risk_per_share <= 0:
            return 0
        return int(risk_dollars / self.risk_per_share)
    
    def position_value(self, risk_dollars: float) -> float:
        """Calculate position value for a given dollar risk."""
        shares = self.shares_for_risk(risk_dollars)
        return shares * self.current_price


class StopRecommender:
    """
    Generates dynamic stop-loss recommendations based on volatility.
    
    Usage:
        recommender = StopRecommender()
        rec = recommender.analyze("NVDA")
        print(rec)
        
        # With entry price
        rec = recommender.analyze("NVDA", entry_price=140.0)
    """
    
    def __init__(
        self,
        data_provider=None,
        config=None
    ):
        """
        Initialize the recommender.
        
        Args:
            data_provider: DataProvider instance (defaults to YFinance)
            config: Config instance (defaults to DEFAULT_CONFIG)
        """
        self.data_provider = data_provider or YFinanceProvider()
        self.config = config or DEFAULT_CONFIG
    
    def analyze(
        self,
        ticker: str,
        entry_price: Optional[float] = None,
        entry_date: Optional[datetime] = None,
        atr_period: int = None,
        base_multiplier: float = None,
        use_regime_adjustment: bool = True,
        data_period: str = None
    ) -> StopRecommendation:
        """
        Generate a complete stop-loss recommendation for a ticker.
        
        Args:
            ticker: Stock symbol
            entry_price: Your entry price (optional, affects initial stop calc)
            entry_date: Your entry date (optional, for finding high since entry)
            atr_period: ATR period (defaults to config)
            base_multiplier: Base ATR multiplier (defaults to config)
            use_regime_adjustment: Whether to adjust multiplier based on vol regime
            data_period: How much historical data to fetch
            
        Returns:
            StopRecommendation with full analysis
        """
        # Apply defaults from config
        atr_period = atr_period or self.config.atr.default_period
        base_multiplier = base_multiplier or self.config.trailing_stop.base_multiplier
        data_period = data_period or self.config.default_data_period
        
        # Fetch data
        df = self.data_provider.get_ohlcv(ticker, period=data_period)
        current_price = float(df['Close'].iloc[-1])
        
        # Compute ATR (multiple periods for context)
        atr_14_result = compute_atr(df, period=14)
        atr_7_result = compute_atr(df, period=7) if len(df) > 8 else None
        atr_21_result = compute_atr(df, period=21) if len(df) > 22 else None
        
        # Use the requested period for main calculation
        if atr_period == 14:
            main_atr = atr_14_result.current_atr
        else:
            main_atr = compute_atr(df, period=atr_period).current_atr
        
        # Analyze volatility regime
        vol_regime = compute_volatility_regime(
            df, 
            atr_period=atr_period,
            lookback_days=self.config.volatility_regime.lookback_days
        )
        
        # Determine multiplier
        if use_regime_adjustment:
            adjusted_multiplier = get_regime_multiplier(
                vol_regime,
                base_multiplier=base_multiplier,
                adjustments=self.config.trailing_stop.regime_adjustments
            )
        else:
            adjusted_multiplier = base_multiplier
        
        # Find recent high (anchor for trailing stop)
        lookback = self.config.trailing_stop.recent_high_lookback
        recent_high, recent_high_date = find_recent_high(
            df,
            lookback_days=lookback if entry_date is None else None,
            entry_date=entry_date
        )
        
        # Compute trailing stop
        stop_result = compute_trailing_stop(
            current_price=current_price,
            recent_high=recent_high,
            recent_high_date=recent_high_date,
            atr=main_atr,
            multiplier=adjusted_multiplier,
            ticker=ticker,
            atr_period=atr_period
        )
        
        # Calculate initial stop if entry price provided
        initial_stop = None
        if entry_price is not None:
            initial_stop = entry_price - (adjusted_multiplier * main_atr)
        
        return StopRecommendation(
            ticker=ticker,
            current_price=current_price,
            suggested_stop=stop_result.stop_level,
            stop_distance_pct=stop_result.stop_distance_pct,
            atr_14=atr_14_result.current_atr,
            atr_7=atr_7_result.current_atr if atr_7_result else None,
            atr_21=atr_21_result.current_atr if atr_21_result else None,
            base_multiplier=base_multiplier,
            regime_adjusted_multiplier=adjusted_multiplier,
            volatility_regime=vol_regime,
            recent_high=recent_high,
            recent_high_date=recent_high_date,
            entry_price=entry_price,
            initial_stop=initial_stop,
            risk_per_share=stop_result.risk_per_share,
            generated_at=datetime.now(),
            data_period=data_period
        )
    
    def analyze_watchlist(
        self,
        tickers: Optional[List[str]] = None,
        **kwargs
    ) -> List[StopRecommendation]:
        """
        Analyze multiple tickers at once.
        
        Args:
            tickers: List of symbols (defaults to config watchlist)
            **kwargs: Additional args passed to analyze()
            
        Returns:
            List of StopRecommendation objects
        """
        tickers = tickers or self.config.watchlist
        results = []
        
        for ticker in tickers:
            try:
                rec = self.analyze(ticker, **kwargs)
                results.append(rec)
            except DataProviderError as e:
                print(f"Warning: Could not analyze {ticker}: {e}")
                continue
        
        return results


def format_recommendation(rec: StopRecommendation, verbose: bool = True) -> str:
    """
    Format a StopRecommendation as a readable string.
    
    Args:
        rec: StopRecommendation to format
        verbose: Include extra detail
        
    Returns:
        Formatted string
    """
    lines = [
        f"{'='*50}",
        f"  {rec.ticker} - Stop Loss Recommendation",
        f"{'='*50}",
        f"",
        f"  Current Price:     ${rec.current_price:,.2f}",
        f"  Suggested Stop:    ${rec.suggested_stop:,.2f}",
        f"  Stop Distance:     {rec.stop_distance_pct:.1f}%",
        f"",
    ]
    
    if rec.entry_price:
        lines.extend([
            f"  Entry Price:       ${rec.entry_price:,.2f}",
            f"  Initial Stop:      ${rec.initial_stop:,.2f}",
            f"",
        ])
    
    lines.extend([
        f"  ATR Details:",
        f"    ATR(14):         ${rec.atr_14:.2f}",
    ])
    
    if rec.atr_7:
        lines.append(f"    ATR(7):          ${rec.atr_7:.2f}")
    if rec.atr_21:
        lines.append(f"    ATR(21):         ${rec.atr_21:.2f}")
    
    lines.extend([
        f"",
        f"  Multiplier:        {rec.regime_adjusted_multiplier:.1f}x ATR",
    ])
    
    if rec.base_multiplier != rec.regime_adjusted_multiplier:
        lines.append(f"    (Base: {rec.base_multiplier:.1f}x, adjusted for regime)")
    
    if verbose and rec.volatility_regime:
        vr = rec.volatility_regime
        lines.extend([
            f"",
            f"  Volatility Regime: {vr.regime.upper()}",
            f"    Percentile:      {vr.percentile:.0f}th",
            f"    Z-Score:         {vr.z_score:+.2f}",
        ])
    
    lines.extend([
        f"",
        f"  Recent High:       ${rec.recent_high:,.2f}",
        f"    Date:            {rec.recent_high_date.strftime('%Y-%m-%d')}",
        f"",
        f"  Risk per Share:    ${rec.risk_per_share:.2f}",
        f"",
        f"  Position Sizing Examples:",
        f"    $500 risk  →    {rec.shares_for_risk(500):,} shares (${rec.position_value(500):,.0f})",
        f"    $1000 risk →    {rec.shares_for_risk(1000):,} shares (${rec.position_value(1000):,.0f})",
        f"    $2000 risk →    {rec.shares_for_risk(2000):,} shares (${rec.position_value(2000):,.0f})",
        f"",
        f"{'='*50}",
    ])
    
    return "\n".join(lines)
