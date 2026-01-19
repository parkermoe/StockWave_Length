"""
Mark Minervini (SEPA) screener strategy.

Based on Mark Minervini's trend template and Stage 2 breakout methodology:
- Stage 2 uptrend confirmation
- Price above key moving averages (50, 150, 200 day)
- Moving averages in proper alignment  
- Price at least 30% above 52-week low
- Price within 25% of 52-week high
- High relative strength (RS rating > 70)
- Tight consolidation pattern (low volatility after rally)
"""
import sys
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent))
from screeners.base_screener import ScreenerStrategy, ScreenerResult
from screeners.registry import register_screener


@register_screener(name="minervini", description="Mark Minervini's trend template and SEPA methodology")
class MinerviniScreener(ScreenerStrategy):
    """
    Mark Minervini screener implementation (Trend Template).
    
    Looks for stocks in confirmed Stage 2 uptrends with proper MA alignment,
    strong relative strength, and recent consolidation.
    """
    
    def __init__(self):
        # Thresholds
        self.min_pct_above_52w_low = 30.0  # 30%+ above 52-week low
        self.max_pct_from_52w_high = -25.0  # Within 25% of 52-week high
        self.min_rs_rating = 70  # Top 30% relative strength
        self.max_consolidation_volatility = 20.0  # Low volatility period
        
        self.weights = {
            'above_mas': 0.25,
            'ma_alignment': 0.20,
            'above_52w_low': 0.15,
            'near_52w_high': 0.10,
            'relative_strength': 0.20,
            'tight_consolidation': 0.10
        }
    
    def get_name(self) -> str:
        return "minervini"
    
    def get_description(self) -> str:
        return (
            "Mark Minervini Trend Template: Screens for Stage 2 uptrend stocks with price above all "
            "key moving averages, proper MA alignment, strong price structure, high relative strength, "
            "and tight consolidation. Best for identifying breakout setups in emerging trends."
        )
    
    def get_criteria(self) -> List[str]:
        return [
            'above_mas',
            'ma_alignment',
            'above_52w_low',
            'near_52w_high',
            'relative_strength',
            'tight_consolidation'
        ]
    
    def get_config(self) -> Dict[str, Any]:
        return {
            'min_pct_above_52w_low': self.min_pct_above_52w_low,
            'max_pct_from_52w_high': self.max_pct_from_52w_high,
            'min_rs_rating': self.min_rs_rating,
            'max_consolidation_volatility': self.max_consolidation_volatility
        }
    
    def filter(
        self,
        ticker: str,
        fundamental_data: Dict[str, Any],
        technical_data: Dict[str, Any]
    ) -> ScreenerResult:
        """Filter a ticker based on Minervini criteria."""
        
        passed_criteria = []
        failed_criteria = []
        notes = []
        
        # 1. Price above all key moving averages (50, 150, 200)
        above_ma_50 = fundamental_data.get('price_vs_ma_50', -100) > 0
        above_ma_150 = fundamental_data.get('price_vs_ma_150', -100) > 0
        above_ma_200 = fundamental_data.get('price_vs_ma_200', -100) > 0
        
        if above_ma_50 and above_ma_150 and above_ma_200:
            passed_criteria.append('above_mas')
            notes.append("Price above all MAs")
        else:
            failed_criteria.append('above_mas')
            notes.append(f"Price MA: 50{'✓' if above_ma_50 else '✗'} 150{'✓' if above_ma_150 else '✗'} 200{'✓' if above_ma_200 else '✗'}")
        
        # 2. Moving average alignment (50 > 150 > 200)
        ma_50_above_150 = fundamental_data.get('ma_50_above_ma_150', False)
        ma_50_above_200 = fundamental_data.get('ma_50_above_ma_200', False)
        ma_150_above_200 = fundamental_data.get('ma_150_above_ma_200', False)
        
        if ma_50_above_150 and ma_50_above_200 and ma_150_above_200:
            passed_criteria.append('ma_alignment')
            notes.append("MA alignment: 50>150>200")
        else:
            failed_criteria.append('ma_alignment')
            notes.append("MA alignment not ideal")
        
        # 3. Price at least 30% above 52-week low
        pct_from_low = fundamental_data.get('price_pct_from_52w_low', 0)
        if pct_from_low >= self.min_pct_above_52w_low:
            passed_criteria.append('above_52w_low')
            notes.append(f"+{pct_from_low:.0f}% from 52w low")
        else:
            failed_criteria.append('above_52w_low')
            notes.append(f"+{pct_from_low:.0f}% from 52w low (needs +{self.min_pct_above_52w_low}%)")
        
        # 4. Price within 25% of 52-week high
        pct_from_high = fundamental_data.get('price_pct_from_52w_high', -100)
        if pct_from_high >= self.max_pct_from_52w_high:
            passed_criteria.append('near_52w_high')
            notes.append(f"{pct_from_high:.1f}% from 52w high")
        else:
            failed_criteria.append('near_52w_high')
            notes.append(f"{pct_from_high:.1f}% from 52w high (too far)")
        
        # 5. High relative strength
        rs_rating = fundamental_data.get('rs_rating')
        if rs_rating is not None and rs_rating >= self.min_rs_rating:
            passed_criteria.append('relative_strength')
            notes.append(f"RS: {rs_rating:.0f}")
        else:
            failed_criteria.append('relative_strength')
            if rs_rating is not None:
                notes.append(f"RS: {rs_rating:.0f} (needs {self.min_rs_rating}+)")
        
        # 6. Tight consolidation (low recent volatility)
        # Use ATR as proxy for volatility
        atr = fundamental_data.get('atr_14')
        current_price = fundamental_data.get('current_price', 1)
        if atr and current_price:
            atr_pct = (atr / current_price) * 100
            if atr_pct <= self.max_consolidation_volatility:
                passed_criteria.append('tight_consolidation')
                notes.append(f"ATR: {atr_pct:.1f}%")
            else:
                failed_criteria.append('tight_consolidation')
                notes.append(f"ATR: {atr_pct:.1f}% (too volatile)")
        else:
            failed_criteria.append('tight_consolidation')
        
        # Calculate score
        score = self.calculate_score(passed_criteria, self.get_criteria(), self.weights)
        
        # Pass if score >= 75 (stricter than CANSLIM)
        passed = score >= 75
        
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
