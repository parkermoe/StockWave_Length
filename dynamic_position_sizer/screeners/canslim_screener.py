"""
CANSLIM screener strategy.

Based on William O'Neil's CANSLIM methodology:
- C: Current quarterly earnings up 25%+
- A: Annual earnings growth of 25%+
- N: New product, management, or price high
- S: Supply and demand (low supply, high demand = volume surge)
- L: Leader or laggard (relative strength vs market)
- I: Institutional sponsorship
- M: Market direction (handled separately, focuses on individual stock)
"""
import sys
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent))
from screeners.base_screener import ScreenerStrategy, ScreenerResult
from screeners.registry import register_screener


@register_screener(name="canslim", description="William O'Neil's CANSLIM growth stock methodology")
class CANSLIMScreener(ScreenerStrategy):
    """
    CANSLIM screener implementation.
    
    Looks for high-growth stocks with strong institutional support,
    recent price strength, and volume confirmation.
    """
    
    def __init__(self):
        # Configurable thresholds
        self.min_eps_growth_qtrly = 0.25  # 25%
        self.min_eps_growth_annual = 0.25  # 25%
        self.pct_from_52w_high = -15.0  # Within 15% of 52-week high
        self.min_volume_surge = 1.5  # 1.5x average volume
        self.min_rs_rating = 70  # Top 30% relative strength
        self.min_institutional_ownership = 0.10  # 10%+ institutional
        
        # Weights for scoring
        self.weights = {
            'current_earnings': 0.20,
            'annual_earnings': 0.20,
            'near_high': 0.15,
            'volume_surge': 0.15,
            'relative_strength': 0.20,
            'institutional': 0.10
        }
    
    def get_name(self) -> str:
        return "canslim"
    
    def get_description(self) -> str:
        return (
            "CANSLIM (William O'Neil): Screens for high-growth stocks with strong earnings growth, "
            "price near 52-week highs, volume confirmation, relative strength, and institutional support. "
            "Best for identifying breakout candidates in bull markets."
        )
    
    def get_criteria(self) -> List[str]:
        return [
            'current_earnings',
            'annual_earnings',
            'near_high',
            'volume_surge',
            'relative_strength',
            'institutional'
        ]
    
    def get_config(self) -> Dict[str, Any]:
        return {
            'min_eps_growth_qtrly': self.min_eps_growth_qtrly,
            'min_eps_growth_annual': self.min_eps_growth_annual,
            'pct_from_52w_high': self.pct_from_52w_high,
            'min_volume_surge': self.min_volume_surge,
            'min_rs_rating': self.min_rs_rating,
            'min_institutional_ownership': self.min_institutional_ownership
        }
    
    def filter(
        self,
        ticker: str,
        fundamental_data: Dict[str, Any],
        technical_data: Dict[str, Any]
    ) -> ScreenerResult:
        """Filter a ticker based on CANSLIM criteria."""
        
        passed_criteria = []
        failed_criteria = []
        notes = []
        
        # C: Current quarterly earnings
        eps_growth_qtrly = fundamental_data.get('earnings_growth_qtrly')
        if eps_growth_qtrly is not None and eps_growth_qtrly >= self.min_eps_growth_qtrly:
            passed_criteria.append('current_earnings')
            notes.append(f"EPS growth Q/Q: {eps_growth_qtrly*100:.1f}%")
        else:
            failed_criteria.append('current_earnings')
            if eps_growth_qtrly is not None:
                notes.append(f"EPS growth Q/Q: {eps_growth_qtrly*100:.1f}% (needs {self.min_eps_growth_qtrly*100}%+)")
        
        # A: Annual earnings growth
        eps_growth_annual = fundamental_data.get('earnings_growth_annual')
        if eps_growth_annual is not None and eps_growth_annual >= self.min_eps_growth_annual:
            passed_criteria.append('annual_earnings')
            notes.append(f"EPS growth annual: {eps_growth_annual*100:.1f}%")
        else:
            failed_criteria.append('annual_earnings')
            if eps_growth_annual is not None:
                notes.append(f"EPS growth annual: {eps_growth_annual*100:.1f}% (needs {self.min_eps_growth_annual*100}%+)")
        
        # N: New high (price within 15% of 52-week high)
        pct_from_high = fundamental_data.get('price_pct_from_52w_high', -100)
        if pct_from_high >= self.pct_from_52w_high:
            passed_criteria.append('near_high')
            notes.append(f"Price {pct_from_high:.1f}% from 52w high")
        else:
            failed_criteria.append('near_high')
            notes.append(f"Price {pct_from_high:.1f}% from 52w high (needs >={self.pct_from_52w_high}%)")
        
        # S: Supply/demand (volume surge)
        volume_surge = fundamental_data.get('volume_surge_ratio', 0)
        if volume_surge >= self.min_volume_surge:
            passed_criteria.append('volume_surge')
            notes.append(f"Volume {volume_surge:.1f}x average")
        else:
            failed_criteria.append('volume_surge')
            notes.append(f"Volume {volume_surge:.1f}x average (needs {self.min_volume_surge}x+)")
        
        # L: Leader (relative strength)
        rs_rating = fundamental_data.get('rs_rating')
        if rs_rating is not None and rs_rating >= self.min_rs_rating:
            passed_criteria.append('relative_strength')
            notes.append(f"RS Rating: {rs_rating:.0f}")
        else:
            failed_criteria.append('relative_strength')
            if rs_rating is not None:
                notes.append(f"RS Rating: {rs_rating:.0f} (needs {self.min_rs_rating}+)")
        
        # I: Institutional sponsorship
        institutional = fundamental_data.get('institutional_ownership')
        if institutional is not None and institutional >= self.min_institutional_ownership:
            passed_criteria.append('institutional')
            notes.append(f"Institutional: {institutional*100:.1f}%")
        else:
            failed_criteria.append('institutional')
            if institutional is not None:
                notes.append(f"Institutional: {institutional*100:.1f}% (needs {self.min_institutional_ownership*100}%+)")
        
        # Calculate score
        score = self.calculate_score(passed_criteria, self.get_criteria(), self.weights)
        
        # Pass if score >= 70
        passed = score >= 70
        
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
