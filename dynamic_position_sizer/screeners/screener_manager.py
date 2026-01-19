"""
Screener Manager - Orchestration engine for stock screening.

Coordinates universe selection, data fetching, screening, and position sizing.
"""
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from screeners import get_screener, list_screeners, ScreenerResult
from data import (
    get_universe,
    FundamentalsProvider,
    FundamentalData,
    UniverseFilter
)
from position import StopRecommender, StopRecommendation
from indicators import AnalystScoring, AnalystScore
from config import DEFAULT_CONFIG


@dataclass
class ScreenOutput:
    """Complete output from a screening run."""
    ticker: str
    screener_result: ScreenerResult
    stop_recommendation: Optional[StopRecommendation] = None
    screener_scores: Dict[str, float] = field(default_factory=dict)  # strategy_name -> score
    analyst_score: Optional[AnalystScore] = None  # Analyst scoring breakdown
    base_score: Optional[float] = None  # Score before analyst multiplier
    
    def __str__(self) -> str:
        multiplier_str = f" (×{self.analyst_score.multiplier:.2f})" if self.analyst_score else ""
        return (
            f"{self.ticker}: Score {self.screener_result.score:.0f}/100{multiplier_str} "
            f"({'PASS' if self.screener_result.passed else 'FAIL'})"
        )


@dataclass
class ScreenSummary:
    """Summary of screening results."""
    strategy_names: List[str]
    total_universe: int
    passed_screener: int
    analyzed_positions: int
    results: List[ScreenOutput]
    execution_time_seconds: float
    combine_mode: str = "union"
    generated_at: datetime = field(default_factory=datetime.now)
    
    def get_top_n(self, n: int = 10) -> List[ScreenOutput]:
        """Get top N results by score."""
        sorted_results = sorted(self.results, key=lambda x: x.screener_result.score, reverse=True)
        return sorted_results[:n]
    
    def get_passing_only(self) -> List[ScreenOutput]:
        """Get only results that passed the screener."""
        return [r for r in self.results if r.screener_result.passed]


class ScreenerManager:
    """
    Main orchestration class for stock screening.
    
    Coordinates:
    1. Universe selection (S&P 500, NASDAQ-100, custom)
    2. Fundamental data fetching with caching
    3. Running screener strategies
    4. Position sizing via StopRecommender
    5. Results aggregation and ranking
    """
    
    def __init__(
        self,
        universe: str = "sp500",
        use_cache: bool = True,
        max_workers: int = 5
    ):
        """
        Initialize the screener manager.
        
        Args:
            universe: Universe to screen ('sp500', 'nasdaq100', 'custom')
            use_cache: Whether to use caching for fundamentals
            max_workers: Max concurrent threads for data fetching
        """
        self.universe_name = universe
        self.universe_provider = get_universe(universe)
        self.fundamentals_provider = FundamentalsProvider(use_cache=use_cache)
        self.stop_recommender = StopRecommender()
        self.max_workers = max_workers
        
        # Get config
        from config import DEFAULT_CONFIG
        self.config = DEFAULT_CONFIG
    
    def run_screen(
        self,
        strategy_names: List[str],
        combine_mode: Literal["union", "intersection"] = "union",
        min_score: Optional[float] = None,
        max_results: Optional[int] = None,
        apply_filters: bool = True,
        calculate_positions: bool = True,
        progress_callback: Optional[callable] = None,
        # Enhanced filtering options
        cap_categories: Optional[List[str]] = None,
        sectors: Optional[List[str]] = None,
        exclude_sectors: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,
        exclude_industries: Optional[List[str]] = None
    ) -> ScreenSummary:
        """
        Run stock screen with specified strategies.
        
        Args:
            strategy_names: List of screener strategy names to run
            combine_mode: How to combine multiple strategies ('union' or 'intersection')
            min_score: Minimum score threshold (0-100)
            max_results: Maximum number of results to return
            apply_filters: Whether to apply liquidity filters
            calculate_positions: Whether to calculate position sizing
            progress_callback: Optional callback(current, total, message) for progress
            cap_categories: Market cap categories to include ('mega', 'large', 'mid', 'small', 'micro')
            sectors: List of sectors to include (optional)
            exclude_sectors: List of sectors to exclude (optional)
            industries: List of industries to include (optional)
            exclude_industries: List of industries to exclude (optional)
            
        Returns:
            ScreenSummary with results
        """
        start_time = time.time()
        
        # Validate strategies
        available_strategies = list_screeners()
        for name in strategy_names:
            if name not in available_strategies:
                raise ValueError(
                    f"Unknown screener '{name}'. Available: {available_strategies}"
                )
        
        # Get screener instances
        screeners = {name: get_screener(name) for name in strategy_names}
        
        # Get universe
        if progress_callback:
            progress_callback(0, 100, f"Loading {self.universe_name} universe...")
        
        tickers = self.universe_provider.get_tickers()
        total_universe = len(tickers)
        
        if progress_callback:
            progress_callback(5, 100, f"Loaded {total_universe} tickers")
        
        # Fetch fundamentals with progress tracking
        fundamentals = self._fetch_fundamentals_parallel(
            tickers,
            progress_callback=progress_callback
        )
        
        # Apply filters if requested
        if apply_filters:
            if progress_callback:
                progress_callback(70, 100, "Applying filters...")
            
            universe_filter = UniverseFilter(
                min_price=self.config.screener.min_price,
                min_volume=self.config.screener.min_volume,
                cap_categories=cap_categories,
                sectors=sectors,
                exclude_sectors=exclude_sectors,
                industries=industries,
                exclude_industries=exclude_industries
            )
            tickers = universe_filter.filter_tickers(tickers, fundamentals)
            
            if progress_callback:
                progress_callback(75, 100, f"Filtered to {len(tickers)} stocks")
                progress_callback(75, 100, f"Filtered to {len(tickers)} liquid stocks")
        
        # Run screeners
        if progress_callback:
            progress_callback(80, 100, f"Running {len(strategy_names)} screener(s)...")
        
        # Initialize analyst scoring if enabled
        analyst_scoring = None
        if self.config.analyst_scoring.enabled:
            analyst_scoring = AnalystScoring(
                weight_upside=self.config.analyst_scoring.weight_upside,
                weight_sentiment=self.config.analyst_scoring.weight_sentiment,
                weight_momentum=self.config.analyst_scoring.weight_momentum,
                weight_coverage=self.config.analyst_scoring.weight_coverage,
                min_multiplier=self.config.analyst_scoring.min_multiplier,
                max_multiplier=self.config.analyst_scoring.max_multiplier,
                min_analyst_count=self.config.analyst_scoring.min_analyst_count
            )
        
        results_by_ticker = {}
        
        for ticker in tickers:
            fund_data = fundamentals.get(ticker)
            if not fund_data:
                continue
            
            # Convert FundamentalData to dict for screeners
            fund_dict = fund_data.to_dict() if hasattr(fund_data, 'to_dict') else fund_data
            tech_dict = {}  # Technical data can be added later
            
            # Run all screeners for this ticker
            screener_results = {}
            for strat_name, screener in screeners.items():
                result = screener.filter(ticker, fund_dict, tech_dict)
                screener_results[strat_name] = result
            
            # Combine results based on mode
            if combine_mode == "intersection":
                # Must pass ALL screeners
                passed = all(r.passed for r in screener_results.values())
                # Use average score
                avg_score = sum(r.score for r in screener_results.values()) / len(screener_results)
                # Use first screener's result as template
                combined_result = list(screener_results.values())[0]
                combined_result.passed = passed
                combined_result.score = avg_score
            else:
                # Union: passes if ANY screener passes
                passed = any(r.passed for r in screener_results.values())
                # Use max score
                max_score = max(r.score for r in screener_results.values())
                combined_result = max(screener_results.values(), key=lambda r: r.score)
                combined_result.passed = passed
                combined_result.score = max_score
            
            # Store base score before analyst adjustment
            base_score = combined_result.score
            
            # Apply analyst multiplier if enabled
            analyst_score = None
            if analyst_scoring and fund_data:
                analyst_score = analyst_scoring.calculate_from_fundamentals(fund_data)
                # Apply multiplier to score
                combined_result.score = combined_result.score * analyst_score.multiplier
            
            # Apply min_score filter
            if min_score and combined_result.score < min_score:
                continue
            
            # Store scores from each strategy
            scores = {name: result.score for name, result in screener_results.items()}
            
            results_by_ticker[ticker] = ScreenOutput(
                ticker=ticker,
                screener_result=combined_result,
                screener_scores=scores,
                analyst_score=analyst_score,
                base_score=base_score
            )
        
        passed_screener = len(results_by_ticker)
        
        if progress_callback:
            progress_callback(90, 100, f"Found {passed_screener} candidates")
        
        # Calculate position sizing for passing stocks
        if calculate_positions:
            if progress_callback:
                progress_callback(92, 100, "Calculating position sizing...")
            
            for ticker, output in results_by_ticker.items():
                try:
                    rec = self.stop_recommender.analyze(ticker)
                    output.stop_recommendation = rec
                except Exception as e:
                    print(f"Warning: Could not analyze {ticker}: {e}")
        
        # Sort by score and apply max_results
        all_results = list(results_by_ticker.values())
        all_results.sort(key=lambda x: x.screener_result.score, reverse=True)
        
        if max_results:
            all_results = all_results[:max_results]
        
        execution_time = time.time() - start_time
        
        if progress_callback:
            progress_callback(100, 100, f"Screen complete in {execution_time:.1f}s")
        
        return ScreenSummary(
            strategy_names=strategy_names,
            total_universe=total_universe,
            passed_screener=passed_screener,
            analyzed_positions=len([r for r in all_results if r.stop_recommendation]),
            results=all_results,
            execution_time_seconds=execution_time,
            combine_mode=combine_mode
        )
    
    def _fetch_fundamentals_parallel(
        self,
        tickers: List[str],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Fetch fundamentals for multiple tickers in parallel.
        
        Uses ThreadPoolExecutor with rate limiting.
        """
        fundamentals = {}
        total = len(tickers)
        completed = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_ticker = {
                executor.submit(self.fundamentals_provider.get_fundamentals, ticker): ticker
                for ticker in tickers
            }
            
            # Process as they complete
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                completed += 1
                
                try:
                    fund_data = future.result()
                    if fund_data:
                        fundamentals[ticker] = fund_data
                    
                    if progress_callback and completed % 10 == 0:
                        progress_pct = 10 + int((completed / total) * 60)  # 10-70%
                        progress_callback(progress_pct, 100, f"Fetching data: {completed}/{total}")
                    
                    # Rate limiting: small delay every N requests
                    if completed % 50 == 0:
                        time.sleep(1)
                        
                except Exception as e:
                    print(f"Error fetching {ticker}: {e}")
        
        return fundamentals
