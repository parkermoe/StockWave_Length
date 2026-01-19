# Dynamic Position Sizer

A Python tool for computing **optimal trailing stop-losses** based on ATR (Average True Range) and volatility regime analysis. The core idea: stops should "breathe" with the stock's volatility.

## Why This Exists

Ever get shaken out of a trade by a stop that was too tight, only to watch the stock rally right after? This tool helps you set stops that respect a stock's natural volatility — wider stops for volatile names, tighter stops for calm ones.

## Features

- **ATR-based trailing stops**: Stops that adapt to each stock's volatility
- **Volatility regime detection**: Classifies current vol as low/normal/elevated/extreme
- **Automatic regime adjustment**: Tighter stops in low-vol, wider in high-vol
- **Position sizing helpers**: Calculate shares based on dollar risk
- **Multiple ATR methods**: Wilder's smoothing, SMA, or EMA
- **Beautiful CLI output**: Rich terminal formatting with color-coded regimes

## Installation

```bash
cd dynamic_position_sizer
pip install -r requirements.txt
```

Requirements:
- Python 3.10+
- yfinance, pandas, numpy, typer, rich

## Quick Start

### Command Line

```bash
# Analyze a single ticker
python cli.py analyze NVDA

# With your entry price (calculates initial stop)
python cli.py analyze NVDA --entry 140

# Multiple tickers with summary table
python cli.py analyze NVDA TSLA AAPL --summary

# Custom ATR multiplier
python cli.py analyze NVDA --multiplier 2.5

# Analyze your watchlist
python cli.py watchlist

# Quick one-liner output
python cli.py quick NVDA

# Use simulated data (when network unavailable)
python cli.py analyze NVDA --mock
```

### As a Library

```python
from main import analyze_ticker, analyze_watchlist

# Single ticker
rec = analyze_ticker("NVDA", entry_price=140.0)
print(f"Stop at ${rec.suggested_stop:.2f}")
print(f"Risk per share: ${rec.risk_per_share:.2f}")

# Position sizing: how many shares for $1000 risk?
shares = rec.shares_for_risk(1000)
print(f"Buy {shares} shares")

# Analyze multiple tickers
recommendations = analyze_watchlist(["NVDA", "TSLA", "AAPL"])
```

## How It Works

### 1. ATR Calculation

Average True Range measures volatility by looking at the full daily range:

```
True Range = max(
    High - Low,
    |High - Previous Close|,
    |Low - Previous Close|
)

ATR = Smoothed average of True Range (default: 14-day Wilder's smoothing)
```

### 2. Volatility Regime Detection

The tool compares current ATR to its historical distribution:

| Regime | Percentile | Recommended Multiplier |
|--------|------------|------------------------|
| Low | 0-25th | 1.5x ATR |
| Normal | 25-75th | 2.0x ATR |
| Elevated | 75-90th | 2.5x ATR |
| Extreme | 90-100th | 3.0x ATR |

### 3. Trailing Stop Calculation

```
Stop Level = Recent High - (Multiplier × ATR)
```

Example: NVDA at $145, recent high $150, ATR $6, regime "normal" (2x):
```
Stop = $150 - (2.0 × $6) = $138
```

## Configuration

Edit `config.py` to customize:

```python
# Default watchlist
watchlist = ["NVDA", "TSLA", "AAPL", "AMD", "META"]

# ATR settings
atr_period = 14  # Standard is 14
atr_method = "wilder"  # or "sma", "ema"

# Regime thresholds (percentiles)
thresholds = {
    "low": 25,
    "normal": 75,
    "elevated": 90,
    "extreme": 100
}

# Multipliers per regime
regime_adjustments = {
    "low": 1.5,
    "normal": 2.0,
    "elevated": 2.5,
    "extreme": 3.0
}
```

## Output Example

```
══════════════════════════════════════════════════════
  NVDA - Stop Loss Recommendation
══════════════════════════════════════════════════════

  Current Price:     $142.50
  Suggested Stop:    $128.86
  Stop Distance:     9.6%

  ATR Details:
    ATR(14):         $6.82
    ATR(7):          $7.15
    ATR(21):         $6.45

  Multiplier:        2.0x ATR

  Volatility Regime: NORMAL
    Percentile:      62nd
    Z-Score:         +0.35

  Recent High:       $142.50
    Date:            2024-01-15

  Risk per Share:    $13.64

  Position Sizing Examples:
    $500 risk  →    36 shares ($5,130)
    $1000 risk →    73 shares ($10,402)
    $2000 risk →    146 shares ($20,805)

══════════════════════════════════════════════════════
```

## Project Structure

```
dynamic_position_sizer/
├── config.py                 # Default parameters
├── data/
│   ├── provider.py           # Abstract data provider interface
│   ├── yfinance_provider.py  # Yahoo Finance implementation
│   └── mock_provider.py      # Synthetic data for testing
├── indicators/
│   ├── atr.py                # ATR calculation
│   └── volatility_regime.py  # Regime classification
├── position/
│   ├── trailing_stop.py      # Stop calculation logic
│   └── stop_recommender.py   # Main orchestrator
├── backtesting/              # (Phase 3 - coming soon)
├── cli.py                    # Command-line interface
├── main.py                   # Entry point
└── requirements.txt
```

## Roadmap

- [x] **Phase 1**: Core ATR + trailing stop + CLI (complete)
- [x] **Phase 2**: Volatility regime detection (complete)
- [ ] **Phase 3**: Support/resistance snapping, backtesting module
- [ ] **Phase 4**: Web dashboard, alerts

## Tips for Use

1. **Don't override the regime adjustment** unless you have a good reason. It's there to protect you.

2. **Use entry price** when you have one — it calculates your initial stop properly.

3. **Watch the percentile**, not just the regime label. 74th percentile (high-normal) is different from 26th percentile (low-normal).

4. **Position size based on risk**, not conviction. If the stop says $10 risk/share and you're willing to lose $500, buy 50 shares — regardless of how bullish you are.

## License

MIT


## Further Contributing
Machine learning integration: Track which screened stocks actually work out (hit profit targets vs stopped out). Use historical data to refine scoring weights automatically. Future enhancement after V1 is stable.