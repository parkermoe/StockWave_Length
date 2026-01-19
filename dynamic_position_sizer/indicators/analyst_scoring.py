"""
Analyst scoring module for calculating composite score multipliers.

Converts analyst data (price targets, recommendations, upgrades) into
a multiplier (0.8x - 1.2x) that adjusts screener scores.
"""
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class AnalystScore:
    """Container for analyst scoring breakdown."""
    upside_score: float  # 0-100
    sentiment_score: float  # 0-100
    momentum_score: float  # 0-100
    coverage_score: float  # 0-100
    composite_score: float  # 0-100 (weighted average)
    multiplier: float  # 0.8-1.2
    
    # Raw metrics for display
    target_upside_pct: Optional[float] = None
    recommendation_mean: Optional[float] = None
    analyst_count: Optional[int] = None
    net_upgrades: int = 0  # upgrades - downgrades


class AnalystScoring:
    """
    Calculate analyst-based score multipliers.
    
    Converts analyst data into a composite multiplier (0.8x - 1.2x) that
    adjusts base screener scores. Configurable weights allow tuning.
    """
    
    def __init__(
        self,
        weight_upside: float = 0.35,
        weight_sentiment: float = 0.30,
        weight_momentum: float = 0.20,
        weight_coverage: float = 0.15,
        min_multiplier: float = 0.8,
        max_multiplier: float = 1.2,
        min_analyst_count: int = 3
    ):
        """
        Initialize analyst scoring engine.
        
        Args:
            weight_upside: Weight for price target upside (default 0.35)
            weight_sentiment: Weight for analyst recommendations (default 0.30)
            weight_momentum: Weight for recent upgrades/downgrades (default 0.20)
            weight_coverage: Weight for analyst coverage depth (default 0.15)
            min_multiplier: Minimum score multiplier (default 0.8)
            max_multiplier: Maximum score multiplier (default 1.2)
            min_analyst_count: Minimum analysts required (default 3)
        """
        # Normalize weights to sum to 1.0
        total_weight = weight_upside + weight_sentiment + weight_momentum + weight_coverage
        self.weight_upside = weight_upside / total_weight
        self.weight_sentiment = weight_sentiment / total_weight
        self.weight_momentum = weight_momentum / total_weight
        self.weight_coverage = weight_coverage / total_weight
        
        self.min_multiplier = min_multiplier
        self.max_multiplier = max_multiplier
        self.min_analyst_count = min_analyst_count
    
    def calculate_score(
        self,
        analyst_target_mean: Optional[float] = None,
        analyst_target_upside_pct: Optional[float] = None,
        analyst_recommendation_mean: Optional[float] = None,
        analyst_count: Optional[int] = None,
        recent_upgrades_30d: int = 0,
        recent_downgrades_30d: int = 0
    ) -> AnalystScore:
        """
        Calculate analyst score and multiplier.
        
        Args:
            analyst_target_mean: Mean price target
            analyst_target_upside_pct: % upside to target
            analyst_recommendation_mean: 1-5 scale (1=Strong Buy, 5=Sell)
            analyst_count: Number of analysts covering
            recent_upgrades_30d: Upgrades in last 30 days
            recent_downgrades_30d: Downgrades in last 30 days
            
        Returns:
            AnalystScore with breakdown and multiplier
        """
        # If insufficient coverage, return neutral score
        if not analyst_count or analyst_count < self.min_analyst_count:
            return AnalystScore(
                upside_score=50.0,
                sentiment_score=50.0,
                momentum_score=50.0,
                coverage_score=0.0,
                composite_score=50.0,
                multiplier=1.0,
                target_upside_pct=analyst_target_upside_pct,
                recommendation_mean=analyst_recommendation_mean,
                analyst_count=analyst_count,
                net_upgrades=recent_upgrades_30d - recent_downgrades_30d
            )
        
        # Calculate individual scores (0-100)
        upside_score = self._score_upside(analyst_target_upside_pct)
        sentiment_score = self._score_sentiment(analyst_recommendation_mean)
        momentum_score = self._score_momentum(recent_upgrades_30d, recent_downgrades_30d)
        coverage_score = self._score_coverage(analyst_count)
        
        # Weighted composite score
        composite_score = (
            upside_score * self.weight_upside +
            sentiment_score * self.weight_sentiment +
            momentum_score * self.weight_momentum +
            coverage_score * self.weight_coverage
        )
        
        # Convert to multiplier (0.8 - 1.2)
        # 50 = neutral (1.0x), 0 = min (0.8x), 100 = max (1.2x)
        multiplier = self._score_to_multiplier(composite_score)
        
        return AnalystScore(
            upside_score=upside_score,
            sentiment_score=sentiment_score,
            momentum_score=momentum_score,
            coverage_score=coverage_score,
            composite_score=composite_score,
            multiplier=multiplier,
            target_upside_pct=analyst_target_upside_pct,
            recommendation_mean=analyst_recommendation_mean,
            analyst_count=analyst_count,
            net_upgrades=recent_upgrades_30d - recent_downgrades_30d
        )
    
    def _score_upside(self, upside_pct: Optional[float]) -> float:
        """
        Score price target upside (0-100).
        
        50% upside = 100 score
        0% upside = 50 score (neutral)
        -20% downside = 0 score
        """
        if upside_pct is None:
            return 50.0
        
        if upside_pct >= 50:
            return 100.0
        elif upside_pct >= 0:
            # 0% to 50% maps to 50-100
            return 50.0 + (upside_pct / 50.0) * 50.0
        else:
            # Negative upside: -20% to 0% maps to 0-50
            return max(0.0, 50.0 + (upside_pct / 20.0) * 50.0)
    
    def _score_sentiment(self, recommendation_mean: Optional[float]) -> float:
        """
        Score analyst recommendations (0-100).
        
        1.0 (Strong Buy) = 100
        2.0 (Buy) = 75
        3.0 (Hold) = 50
        4.0 (Sell) = 25
        5.0 (Strong Sell) = 0
        """
        if recommendation_mean is None:
            return 50.0
        
        # Clamp to 1-5 range
        rec = max(1.0, min(5.0, recommendation_mean))
        
        # Linear mapping: 1->100, 5->0
        return 100.0 - ((rec - 1.0) / 4.0) * 100.0
    
    def _score_momentum(self, upgrades: int, downgrades: int) -> float:
        """
        Score recent upgrade/downgrade momentum (0-100).
        
        Net +3 or more = 100
        Net 0 = 50 (neutral)
        Net -3 or more = 0
        """
        net = upgrades - downgrades
        
        if net >= 3:
            return 100.0
        elif net <= -3:
            return 0.0
        else:
            # Linear mapping: -3->0, 0->50, +3->100
            return 50.0 + (net / 3.0) * 50.0
    
    def _score_coverage(self, analyst_count: Optional[int]) -> float:
        """
        Score analyst coverage depth (0-100).
        
        20+ analysts = 100
        10 analysts = 75
        5 analysts = 50
        3 analysts = 25
        <3 analysts = 0
        """
        if not analyst_count or analyst_count < self.min_analyst_count:
            return 0.0
        
        if analyst_count >= 20:
            return 100.0
        elif analyst_count >= 10:
            # 10-20 -> 75-100
            return 75.0 + ((analyst_count - 10) / 10.0) * 25.0
        elif analyst_count >= 5:
            # 5-10 -> 50-75
            return 50.0 + ((analyst_count - 5) / 5.0) * 25.0
        else:
            # 3-5 -> 25-50
            return 25.0 + ((analyst_count - 3) / 2.0) * 25.0
    
    def _score_to_multiplier(self, score: float) -> float:
        """
        Convert composite score (0-100) to multiplier (min-max).
        
        50 = neutral (1.0x)
        0 = min_multiplier (default 0.8x)
        100 = max_multiplier (default 1.2x)
        """
        # Normalize score to -1 to +1 range (50 = 0)
        normalized = (score - 50.0) / 50.0
        
        # Map to multiplier range
        if normalized >= 0:
            # Positive: 1.0 to max_multiplier
            multiplier = 1.0 + (normalized * (self.max_multiplier - 1.0))
        else:
            # Negative: min_multiplier to 1.0
            multiplier = 1.0 + (normalized * (1.0 - self.min_multiplier))
        
        # Clamp to range
        return max(self.min_multiplier, min(self.max_multiplier, multiplier))
    
    def calculate_from_fundamentals(self, fundamental_data) -> AnalystScore:
        """
        Calculate analyst score from FundamentalData object.
        
        Args:
            fundamental_data: FundamentalData instance with analyst fields
            
        Returns:
            AnalystScore with breakdown and multiplier
        """
        return self.calculate_score(
            analyst_target_mean=fundamental_data.analyst_target_mean,
            analyst_target_upside_pct=fundamental_data.analyst_target_upside_pct,
            analyst_recommendation_mean=fundamental_data.analyst_recommendation_mean,
            analyst_count=fundamental_data.analyst_count,
            recent_upgrades_30d=fundamental_data.recent_upgrades_30d,
            recent_downgrades_30d=fundamental_data.recent_downgrades_30d
        )
