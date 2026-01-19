"""
High Volatility screener strategy.

Screens for stocks with elevated volatility that may present swing trading opportunities.
Looks for recent volatility spikes, momentum, and price action above moving averages.
"""
import sys
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent))
from screeners.base_screener import ScreenerStrategy, ScreenerResult
from screeners.registry import register_screener


@register_screener(name="high_volatility", description="High volatility swing trading candidates")
class HighVolatilityScreener(ScreenerStrategy):
    """
    High volatility screener.
    
    Targets stocks with elevated volatility for active swing trading.
    Combines volatility metrics with momentum and trend filters.
    """
    
    def __init__(self):
        self.min_atr_percentile = 75  # ATR in top 25%
        self.min_volume_surge = 1.3  # Above average volume
        self.min_momentum_3m = 10.0  # Up 10%+ in 3 months
        self.min_beta = 1.2  # More volatile than market
        
        self.weights = {
            'high_atr': 0.30,
            'volume_surge': 0.20,
            'momentum': 0.25,
            'above_ma': 0.15,
            'high_beta': 0.10
        }
    
    def get_name(self) -> str:
        return "high_volatility"
    
    def get_description(self) -> str:
        return (
            "High Volatility: Screens for stocks with elevated volatility (high ATR percentile), "
            "above-average volume, positive momentum, and beta >1.2. Best for active swing traders "
            "looking for stocks with large intraday/daily price swings."
        )
    
    def get_criteria(self) -> List[str]:
        return [
            'high_atr',
            'volume_surge',
            'momentum',
            'above_ma',
            'high_beta'
        ]
    
    def get_config(self) -> Dict[str, Any]:
        return {
            'min_atr_percentile': self.min_atr_percentile,
            'min_volume_surge': self.min_volume_surge,
            'min_momentum_3m': self.min_momentum_3m,
            'min_beta': self.min_beta
        }
    
    def filter(
        self,
        ticker: str,
        fundamental_data: Dict[str, Any],
        technical_data: Dict[str, Any]
    ) -> ScreenerResult:
        """Filter a ticker based on volatility criteria."""
        
        passed_criteria = []
        failed_criteria = []
        notes = []
        
        # 1. High ATR (use price-relative ATR as proxy for percentile)
        atr = fundamental_data.get('atr_14')
        current_price = fundamental_data.get('current_price', 1)
        if atr and current_price:
            atr_pct = (atr / current_price) * 100
            # High volatility if ATR > 5% of price (rough heuristic)
            if atr_pct >= 5.0:
                passed_criteria.append('high_atr')
                notes.append(f"ATR: {atr_pct:.1f}% of price")
            else:
                failed_criteria.append('high_atr')
                notes.append(f"ATR: {atr_pct:.1f}% (needs >5%)")
        else:
            failed_criteria.append('high_atr')
        
        # 2. Volume surge
        volume_surge = fundamental_data.get('volume_surge_ratio', 0)
        if volume_surge >= self.min_volume_surge:
            passed_criteria.append('volume_surge')
            notes.append(f"Vol: {volume_surge:.1f}x avg")
        else:
            failed_criteria.append('volume_surge')
            notes.append(f"Vol: {volume_surge:.1f}x avg (needs {self.min_volume_surge}x+)")
        
        # 3. Positive momentum
        momentum_3m = fundamental_data.get('price_momentum_3m', -100)
        if momentum_3m >= self.min_momentum_3m:
            passed_criteria.append('momentum')
            notes.append(f"3M momentum: +{momentum_3m:.1f}%")
        else:
            failed_criteria.append('momentum')
            notes.append(f"3M momentum: {momentum_3m:+.1f}% (needs +{self.min_momentum_3m}%)")
        
        # 4. Above 10-day MA (short-term trend filter)
        price_vs_ma_50 = fundamental_data.get('price_vs_ma_50', -100)
        if price_vs_ma_50 > 0:
            passed_criteria.append('above_ma')
            notes.append("Above MA50")
        else:
            failed_criteria.append('above_ma')
            notes.append("Below MA50")
        
        # 5. High beta
        beta = fundamental_data.get('beta')
        if beta is not None and beta >= self.min_beta:
            passed_criteria.append('high_beta')
            notes.append(f"Beta: {beta:.2f}")
        else:
            failed_criteria.append('high_beta')
            if beta is not None:
                notes.append(f"Beta: {beta:.2f} (needs {self.min_beta}+)")
        
        # Calculate score
        score = self.calculate_score(passed_criteria, self.get_criteria(), self.weights)
        
        # Pass if score >= 65
        passed = score >= 65
        
        return ScreenerResult(
            ticker=ticker,
            score=score,
            passed=passed,
            passed_criteria=passed_criteria,
            failed_criteria=failed_criteria,
            fundamental_data=fundamental_data,
            technical_data=technical_data,
            notes=" | ".join(notes)
        )
