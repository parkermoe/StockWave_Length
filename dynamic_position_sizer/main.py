#!/usr/bin/env python3
"""
Dynamic Position Sizer - Main Entry Point

A tool for computing optimal trailing stop-losses based on 
ATR (Average True Range) and volatility regime analysis.

Usage:
    # As a CLI tool
    python main.py NVDA
    python main.py NVDA --entry 140
    
    # As a library
    from main import analyze_ticker
    rec = analyze_ticker("NVDA")
"""
from position import StopRecommender, StopRecommendation, format_recommendation
from data import YFinanceProvider
from config import DEFAULT_CONFIG


def analyze_ticker(
    ticker: str,
    entry_price: float = None,
    multiplier: float = 2.0,
    atr_period: int = 14
) -> StopRecommendation:
    """
    Quick analysis function for programmatic use.
    
    Args:
        ticker: Stock symbol
        entry_price: Optional entry price
        multiplier: ATR multiplier (default 2.0)
        atr_period: ATR period (default 14)
        
    Returns:
        StopRecommendation with full analysis
        
    Example:
        >>> rec = analyze_ticker("NVDA", entry_price=140)
        >>> print(f"Stop at ${rec.suggested_stop:.2f}")
    """
    recommender = StopRecommender()
    return recommender.analyze(
        ticker=ticker,
        entry_price=entry_price,
        base_multiplier=multiplier,
        atr_period=atr_period
    )


def analyze_watchlist(tickers: list = None) -> list:
    """
    Analyze multiple tickers.
    
    Args:
        tickers: List of symbols (uses config watchlist if None)
        
    Returns:
        List of StopRecommendation objects
    """
    recommender = StopRecommender()
    return recommender.analyze_watchlist(tickers)


def main():
    """Run the CLI application."""
    from cli import app
    app()


if __name__ == "__main__":
    main()
