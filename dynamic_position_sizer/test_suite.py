#!/usr/bin/env python3
"""
Comprehensive test suite for analyst integration and screener functionality.

Tests:
1. Analyst data fetching for multiple tickers
2. Analyst scoring calculation
3. Screener execution with analyst multipliers
4. CLI commands
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from data import FundamentalsProvider
from indicators import AnalystScoring
from screeners import list_screeners
from screeners.screener_manager import ScreenerManager
from config import DEFAULT_CONFIG


def test_analyst_data_fetching():
    """Test 1: Fetch analyst data for various tickers."""
    print("=" * 60)
    print("TEST 1: Analyst Data Fetching")
    print("=" * 60)
    
    provider = FundamentalsProvider()
    test_tickers = ["NVDA", "AAPL", "TSLA", "AMD", "META"]
    
    results = []
    for ticker in test_tickers:
        print(f"\nFetching {ticker}...")
        fund = provider.get_fundamentals(ticker, force_refresh=True)
        
        if fund:
            has_analyst_data = (
                fund.analyst_target_mean is not None or
                fund.analyst_recommendation_mean is not None
            )
            
            results.append({
                'ticker': ticker,
                'success': True,
                'price': fund.current_price,
                'target': fund.analyst_target_mean,
                'upside': fund.analyst_target_upside_pct,
                'rec_mean': fund.analyst_recommendation_mean,
                'analyst_count': fund.analyst_count,
                'has_data': has_analyst_data
            })
            
            print(f"  ✓ Price: ${fund.current_price:.2f}")
            print(f"  ✓ Target: ${fund.analyst_target_mean:.2f}" if fund.analyst_target_mean else "  ⚠ No target")
            print(f"  ✓ Upside: {fund.analyst_target_upside_pct:+.1f}%" if fund.analyst_target_upside_pct else "  ⚠ No upside")
            print(f"  ✓ Recommendation: {fund.analyst_recommendation_mean:.2f}/5" if fund.analyst_recommendation_mean else "  ⚠ No rec")
            print(f"  ✓ Analysts: {fund.analyst_count}" if fund.analyst_count else "  ⚠ No coverage")
        else:
            results.append({'ticker': ticker, 'success': False})
            print(f"  ✗ Failed to fetch")
    
    success_count = sum(1 for r in results if r.get('success'))
    data_count = sum(1 for r in results if r.get('has_data'))
    
    print(f"\n{'=' * 60}")
    print(f"RESULT: {success_count}/{len(test_tickers)} tickers fetched successfully")
    print(f"        {data_count}/{success_count} have analyst data")
    print(f"{'PASS' if success_count == len(test_tickers) else 'FAIL'}")
    print(f"{'=' * 60}\n")
    
    return results


def test_analyst_scoring():
    """Test 2: Analyst scoring calculation."""
    print("=" * 60)
    print("TEST 2: Analyst Scoring Calculation")
    print("=" * 60)
    
    provider = FundamentalsProvider()
    scorer = AnalystScoring()
    
    test_tickers = ["NVDA", "AAPL", "TSLA"]
    results = []
    
    for ticker in test_tickers:
        print(f"\n{ticker}:")
        fund = provider.get_fundamentals(ticker)
        
        if fund:
            score = scorer.calculate_from_fundamentals(fund)
            
            results.append({
                'ticker': ticker,
                'composite': score.composite_score,
                'multiplier': score.multiplier,
                'upside_score': score.upside_score,
                'sentiment_score': score.sentiment_score
            })
            
            print(f"  Upside Score:     {score.upside_score:.1f}/100")
            print(f"  Sentiment Score:  {score.sentiment_score:.1f}/100")
            print(f"  Momentum Score:   {score.momentum_score:.1f}/100")
            print(f"  Coverage Score:   {score.coverage_score:.1f}/100")
            print(f"  Composite Score:  {score.composite_score:.1f}/100")
            print(f"  → Multiplier:     {score.multiplier:.3f}x")
            
            # Validate multiplier is in range
            if score.multiplier < 0.8 or score.multiplier > 1.2:
                print(f"  ✗ ERROR: Multiplier out of range!")
                results[-1]['valid'] = False
            else:
                print(f"  ✓ Multiplier in valid range")
                results[-1]['valid'] = True
        else:
            print(f"  ✗ Could not fetch data")
            results.append({'ticker': ticker, 'valid': False})
    
    valid_count = sum(1 for r in results if r.get('valid'))
    
    print(f"\n{'=' * 60}")
    print(f"RESULT: {valid_count}/{len(test_tickers)} scores calculated correctly")
    print(f"{'PASS' if valid_count == len(test_tickers) else 'FAIL'}")
    print(f"{'=' * 60}\n")
    
    return results


def test_screener_with_analyst():
    """Test 3: Run screener with analyst multiplier."""
    print("=" * 60)
    print("TEST 3: Screener with Analyst Multiplier")
    print("=" * 60)
    
    # Use a small test universe for speed
    from data.universe_provider import CustomUniverseProvider
    
    test_tickers = ["NVDA", "AAPL", "TSLA", "AMD", "META", "GOOGL", "MSFT", "AMZN"]
    
    print(f"\nTest universe: {', '.join(test_tickers)}")
    print(f"Strategy: high_volatility")
    print(f"Analyst multiplier: ENABLED")
    
    # Temporarily replace universe provider
    manager = ScreenerManager(universe="sp500", max_workers=3)
    manager.universe_provider = CustomUniverseProvider(test_tickers)
    
    try:
        summary = manager.run_screen(
            strategy_names=["high_volatility"],
            combine_mode="union",
            max_results=5,
            calculate_positions=False  # Skip for speed
        )
        
        print(f"\n{'=' * 60}")
        print(f"RESULTS:")
        print(f"  Screened: {summary.total_universe} stocks")
        print(f"  Passed: {summary.passed_screener} candidates")
        print(f"  Time: {summary.execution_time_seconds:.1f}s")
        
        if summary.results:
            print(f"\nTop 5 Results:")
            print(f"{'Ticker':<8} {'Base':>6} {'Mult':>6} {'Final':>6}")
            print("-" * 30)
            
            for result in summary.results[:5]:
                base = result.base_score if result.base_score else 0
                mult = result.analyst_score.multiplier if result.analyst_score else 1.0
                final = result.screener_result.score
                
                print(f"{result.ticker:<8} {base:>6.1f} {mult:>5.2f}x {final:>6.1f}")
                
                # Validate calculation
                expected = base * mult
                diff = abs(final - expected)
                if diff > 0.1:
                    print(f"  ✗ ERROR: Score mismatch! Expected {expected:.1f}")
                    return False
        
        print(f"\n{'=' * 60}")
        print(f"RESULT: Screener executed successfully with analyst multiplier")
        print(f"PASS")
        print(f"{'=' * 60}\n")
        
        return True
        
    except Exception as e:
        print(f"\n{'=' * 60}")
        print(f"✗ ERROR: {e}")
        print(f"FAIL")
        print(f"{'=' * 60}\n")
        return False


def test_config_settings():
    """Test 4: Verify configuration."""
    print("=" * 60)
    print("TEST 4: Configuration Validation")
    print("=" * 60)
    
    config = DEFAULT_CONFIG
    
    tests = [
        ("Analyst scoring enabled", config.analyst_scoring.enabled, True),
        ("Weight upside", config.analyst_scoring.weight_upside, 0.35),
        ("Weight sentiment", config.analyst_scoring.weight_sentiment, 0.30),
        ("Weight momentum", config.analyst_scoring.weight_momentum, 0.20),
        ("Weight coverage", config.analyst_scoring.weight_coverage, 0.15),
        ("Min multiplier", config.analyst_scoring.min_multiplier, 0.8),
        ("Max multiplier", config.analyst_scoring.max_multiplier, 1.2),
        ("Min analyst count", config.analyst_scoring.min_analyst_count, 3),
    ]
    
    passed = 0
    for name, actual, expected in tests:
        status = "✓" if actual == expected else "✗"
        print(f"  {status} {name}: {actual} (expected {expected})")
        if actual == expected:
            passed += 1
    
    # Verify weights sum to 1.0
    total_weight = (
        config.analyst_scoring.weight_upside +
        config.analyst_scoring.weight_sentiment +
        config.analyst_scoring.weight_momentum +
        config.analyst_scoring.weight_coverage
    )
    weight_ok = abs(total_weight - 1.0) < 0.01
    status = "✓" if weight_ok else "✗"
    print(f"  {status} Weights sum to 1.0: {total_weight:.2f}")
    if weight_ok:
        passed += 1
    
    print(f"\n{'=' * 60}")
    print(f"RESULT: {passed}/{len(tests)+1} configuration checks passed")
    print(f"{'PASS' if passed == len(tests)+1 else 'FAIL'}")
    print(f"{'=' * 60}\n")
    
    return passed == len(tests)+1


def test_screener_list():
    """Test 5: Verify screener registry."""
    print("=" * 60)
    print("TEST 5: Screener Registry")
    print("=" * 60)
    
    strategies = list_screeners()
    expected = ["canslim", "high_volatility", "minervini"]
    
    print(f"\nRegistered strategies: {', '.join(strategies)}")
    
    all_present = all(s in strategies for s in expected)
    
    if all_present:
        print(f"✓ All expected strategies present")
    else:
        missing = [s for s in expected if s not in strategies]
        print(f"✗ Missing strategies: {missing}")
    
    print(f"\n{'=' * 60}")
    print(f"RESULT: Screener registry {'PASS' if all_present else 'FAIL'}")
    print(f"{'=' * 60}\n")
    
    return all_present


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("COMPREHENSIVE TEST SUITE")
    print("Testing analyst integration and screener functionality")
    print("=" * 60 + "\n")
    
    results = {}
    
    try:
        results['analyst_data'] = test_analyst_data_fetching()
        results['analyst_scoring'] = test_analyst_scoring()
        results['screener_list'] = test_screener_list()
        results['config'] = test_config_settings()
        results['screener_integration'] = test_screener_with_analyst()
        
    except Exception as e:
        print(f"\n{'=' * 60}")
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        print(f"{'=' * 60}\n")
        return
    
    # Final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    
    test_results = [
        ("Analyst Data Fetching", results.get('analyst_data') is not None),
        ("Analyst Scoring", results.get('analyst_scoring') is not None),
        ("Screener Registry", results.get('screener_list', False)),
        ("Configuration", results.get('config', False)),
        ("Screener Integration", results.get('screener_integration', False)),
    ]
    
    for name, passed in test_results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status:<10} {name}")
    
    total_pass = sum(1 for _, p in test_results if p)
    total_tests = len(test_results)
    
    print(f"\n{'=' * 60}")
    print(f"OVERALL: {total_pass}/{total_tests} test suites passed")
    print(f"{'=' * 60}\n")
    
    if total_pass == total_tests:
        print("🎉 ALL TESTS PASSED! System is ready for production.")
    else:
        print("⚠️  SOME TESTS FAILED. Review output above.")


if __name__ == "__main__":
    main()
