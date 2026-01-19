"""
Base screener strategy interface.

All screener strategies must inherit from ScreenerStrategy and implement
the required methods for filtering stocks.
"""
import sys
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class ScreenerResult:
    """Result from screening a single ticker."""
    ticker: str
    score: float  # 0-100 score indicating how well it matches criteria
    passed: bool  # Whether it passed all required criteria
    passed_criteria: List[str] = field(default_factory=list)
    failed_criteria: List[str] = field(default_factory=list)
    fundamental_data: Dict[str, Any] = field(default_factory=dict)
    technical_data: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    screened_at: datetime = field(default_factory=datetime.now)
    
    def __str__(self) -> str:
        status = "✓ PASS" if self.passed else "✗ FAIL"
        return (
            f"{status} {self.ticker} (Score: {self.score:.0f}/100)\n"
            f"  Passed: {', '.join(self.passed_criteria) if self.passed_criteria else 'None'}\n"
            f"  Failed: {', '.join(self.failed_criteria) if self.failed_criteria else 'None'}"
        )


class ScreenerStrategy(ABC):
    """
    Abstract base class for stock screening strategies.
    
    All screener implementations must inherit from this class and implement
    the required methods.
    
    Example:
        class MyScreener(ScreenerStrategy):
            def get_name(self) -> str:
                return "my_custom_screener"
            
            def filter(self, ticker, fundamental_data, technical_data) -> ScreenerResult:
                # Implement screening logic
                ...
    """
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Return the unique name/ID of this screener.
        
        Used for CLI commands and registry lookups.
        Should be lowercase with underscores (e.g., 'canslim', 'mark_minervini').
        """
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """
        Return a human-readable description of this screening strategy.
        
        Should explain what the screener looks for and its typical use case.
        """
        pass
    
    @abstractmethod
    def get_criteria(self) -> List[str]:
        """
        Return a list of criteria names that this screener evaluates.
        
        Example: ['eps_growth', 'price_near_high', 'volume_surge', 'relative_strength']
        """
        pass
    
    @abstractmethod
    def filter(
        self,
        ticker: str,
        fundamental_data: Dict[str, Any],
        technical_data: Dict[str, Any]
    ) -> ScreenerResult:
        """
        Evaluate a single ticker against this screener's criteria.
        
        Args:
            ticker: Stock symbol
            fundamental_data: Dict with fundamental metrics (earnings, revenue, etc.)
            technical_data: Dict with technical indicators (MAs, ATR, volume, etc.)
            
        Returns:
            ScreenerResult with score, pass/fail status, and details
        """
        pass
    
    def get_config(self) -> Dict[str, Any]:
        """
        Return configuration parameters for this screener.
        
        Override this method to expose tunable parameters.
        Default returns empty dict.
        """
        return {}
    
    def calculate_score(
        self,
        passed_criteria: List[str],
        total_criteria: List[str],
        weights: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Helper method to calculate a 0-100 score based on passed criteria.
        
        Args:
            passed_criteria: List of criteria that passed
            total_criteria: List of all criteria
            weights: Optional dict mapping criterion name to weight (0-1)
            
        Returns:
            Score from 0-100
        """
        if not total_criteria:
            return 0.0
        
        if weights is None:
            # Equal weighting
            return (len(passed_criteria) / len(total_criteria)) * 100
        
        # Weighted scoring
        total_weight = sum(weights.get(c, 1.0) for c in total_criteria)
        passed_weight = sum(weights.get(c, 1.0) for c in passed_criteria)
        
        return (passed_weight / total_weight) * 100 if total_weight > 0 else 0.0
