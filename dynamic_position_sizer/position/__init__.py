"""
Position sizing and stop-loss calculation modules.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from position.trailing_stop import (
    compute_trailing_stop,
    find_recent_high,
    compute_chandelier_exit,
    compute_keltner_stop,
    TrailingStopResult
)
from position.stop_recommender import (
    StopRecommender,
    StopRecommendation,
    format_recommendation
)

__all__ = [
    "compute_trailing_stop",
    "find_recent_high",
    "compute_chandelier_exit",
    "compute_keltner_stop",
    "TrailingStopResult",
    "StopRecommender",
    "StopRecommendation",
    "format_recommendation"
]
