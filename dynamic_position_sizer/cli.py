#!/usr/bin/env python3
"""
Command-line interface for the Dynamic Position Sizer.

Usage:
    python cli.py NVDA
    python cli.py NVDA --entry 140
    python cli.py NVDA TSLA AAPL --multiplier 2.5
    python cli.py watchlist
    python cli.py NVDA --mock  # Use simulated data (for testing)
"""
import typer
from typing import Optional, List
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from data import YFinanceProvider, MockDataProvider, DataProviderError
from position import StopRecommender, StopRecommendation, format_recommendation
from config import DEFAULT_CONFIG

app = typer.Typer(
    name="position-sizer",
    help="Dynamic position sizing and stop-loss calculator based on ATR and volatility regime.",
    invoke_without_command=True
)
console = Console()


def create_recommendation_panel(rec: StopRecommendation) -> Panel:
    """Create a rich Panel for a single recommendation."""
    
    # Regime color coding
    regime_colors = {
        "low": "green",
        "normal": "blue", 
        "elevated": "yellow",
        "extreme": "red"
    }
    regime = rec.volatility_regime
    regime_color = regime_colors.get(regime.regime, "white") if regime else "white"
    
    # Build content
    content = []
    content.append(f"[bold]Current Price:[/bold]     ${rec.current_price:,.2f}")
    content.append(f"[bold cyan]Suggested Stop:[/bold cyan]    ${rec.suggested_stop:,.2f}")
    content.append(f"[bold]Stop Distance:[/bold]     {rec.stop_distance_pct:.1f}%")
    content.append("")
    
    if rec.entry_price:
        content.append(f"[dim]Entry Price:[/dim]        ${rec.entry_price:,.2f}")
        content.append(f"[dim]Initial Stop:[/dim]       ${rec.initial_stop:,.2f}")
        content.append("")
    
    content.append(f"[bold]ATR(14):[/bold]            ${rec.atr_14:.2f}")
    if rec.atr_7:
        content.append(f"[dim]ATR(7):[/dim]             ${rec.atr_7:.2f}")
    if rec.atr_21:
        content.append(f"[dim]ATR(21):[/dim]            ${rec.atr_21:.2f}")
    content.append("")
    
    mult_str = f"{rec.regime_adjusted_multiplier:.1f}x ATR"
    if rec.base_multiplier != rec.regime_adjusted_multiplier:
        mult_str += f" [dim](base: {rec.base_multiplier:.1f}x)[/dim]"
    content.append(f"[bold]Multiplier:[/bold]         {mult_str}")
    
    if regime:
        content.append("")
        content.append(f"[bold]Vol Regime:[/bold]         [{regime_color}]{regime.regime.upper()}[/{regime_color}]")
        content.append(f"[dim]  Percentile:[/dim]       {regime.percentile:.0f}th")
        content.append(f"[dim]  Z-Score:[/dim]          {regime.z_score:+.2f}")
    
    content.append("")
    content.append(f"[bold]Recent High:[/bold]        ${rec.recent_high:,.2f} ({rec.recent_high_date.strftime('%Y-%m-%d')})")
    content.append(f"[bold]Risk/Share:[/bold]         ${rec.risk_per_share:.2f}")
    
    # Position sizing
    content.append("")
    content.append("[bold]Position Sizing:[/bold]")
    for risk in [500, 1000, 2000]:
        shares = rec.shares_for_risk(risk)
        value = rec.position_value(risk)
        content.append(f"  ${risk:,} risk → {shares:,} shares (${value:,.0f})")
    
    return Panel(
        "\n".join(content),
        title=f"[bold white]{rec.ticker}[/bold white]",
        border_style="cyan",
        box=box.ROUNDED
    )


def create_summary_table(recommendations: List[StopRecommendation]) -> Table:
    """Create a summary table for multiple recommendations."""
    table = Table(
        title="Stop Loss Summary",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan"
    )
    
    table.add_column("Ticker", style="bold")
    table.add_column("Price", justify="right")
    table.add_column("Stop", justify="right", style="cyan")
    table.add_column("Distance", justify="right")
    table.add_column("ATR(14)", justify="right")
    table.add_column("Mult", justify="right")
    table.add_column("Regime", justify="center")
    table.add_column("Risk/Sh", justify="right")
    
    regime_colors = {
        "low": "green",
        "normal": "blue",
        "elevated": "yellow", 
        "extreme": "red"
    }
    
    for rec in recommendations:
        regime = rec.volatility_regime
        regime_str = f"[{regime_colors.get(regime.regime, 'white')}]{regime.regime.upper()}[/]" if regime else "-"
        
        table.add_row(
            rec.ticker,
            f"${rec.current_price:,.2f}",
            f"${rec.suggested_stop:,.2f}",
            f"{rec.stop_distance_pct:.1f}%",
            f"${rec.atr_14:.2f}",
            f"{rec.regime_adjusted_multiplier:.1f}x",
            regime_str,
            f"${rec.risk_per_share:.2f}"
        )
    
    return table


@app.command()
def analyze(
    tickers: List[str] = typer.Argument(
        ...,
        help="Stock ticker(s) to analyze (e.g., NVDA TSLA AAPL)"
    ),
    entry: Optional[float] = typer.Option(
        None,
        "--entry", "-e",
        help="Your entry price (for initial stop calculation)"
    ),
    multiplier: float = typer.Option(
        2.0,
        "--multiplier", "-m",
        help="Base ATR multiplier for stop calculation"
    ),
    atr_period: int = typer.Option(
        14,
        "--atr-period", "-p",
        help="ATR calculation period"
    ),
    no_regime_adjust: bool = typer.Option(
        False,
        "--no-regime-adjust",
        help="Disable volatility regime adjustment"
    ),
    summary: bool = typer.Option(
        False,
        "--summary", "-s",
        help="Show summary table only (for multiple tickers)"
    ),
    json_output: bool = typer.Option(
        False,
        "--json", "-j",
        help="Output as JSON"
    ),
    mock: bool = typer.Option(
        False,
        "--mock",
        help="Use simulated data (for testing/demo when network unavailable)"
    )
):
    """
    Analyze stock(s) and generate stop-loss recommendations.
    
    Examples:
    
        python cli.py analyze NVDA
        
        python cli.py analyze NVDA --entry 140
        
        python cli.py analyze NVDA TSLA AAPL --summary
        
        python cli.py analyze NVDA -m 2.5 --no-regime-adjust
        
        python cli.py analyze NVDA --mock  # Use simulated data
    """
    # Select data provider
    if mock:
        data_provider = MockDataProvider(seed=42)
        console.print("[dim]Using simulated data (--mock mode)[/dim]\n")
    else:
        data_provider = YFinanceProvider()
    
    recommender = StopRecommender(data_provider=data_provider)
    recommendations = []
    
    with console.status("[bold green]Fetching data and analyzing..."):
        for ticker in tickers:
            try:
                rec = recommender.analyze(
                    ticker=ticker.upper(),
                    entry_price=entry,
                    atr_period=atr_period,
                    base_multiplier=multiplier,
                    use_regime_adjustment=not no_regime_adjust
                )
                recommendations.append(rec)
            except DataProviderError as e:
                console.print(f"[red]Error analyzing {ticker}: {e}[/red]")
    
    if not recommendations:
        console.print("[red]No valid recommendations generated.[/red]")
        raise typer.Exit(1)
    
    if json_output:
        import json
        output = []
        for rec in recommendations:
            output.append({
                "ticker": rec.ticker,
                "current_price": rec.current_price,
                "suggested_stop": rec.suggested_stop,
                "stop_distance_pct": rec.stop_distance_pct,
                "atr_14": rec.atr_14,
                "multiplier": rec.regime_adjusted_multiplier,
                "regime": rec.volatility_regime.regime if rec.volatility_regime else None,
                "risk_per_share": rec.risk_per_share
            })
        console.print_json(json.dumps(output, indent=2))
        return
    
    if len(recommendations) > 1 and summary:
        console.print(create_summary_table(recommendations))
    elif len(recommendations) > 1:
        console.print(create_summary_table(recommendations))
        console.print()
        for rec in recommendations:
            console.print(create_recommendation_panel(rec))
            console.print()
    else:
        console.print(create_recommendation_panel(recommendations[0]))


@app.command()
def watchlist(
    multiplier: float = typer.Option(
        2.0,
        "--multiplier", "-m",
        help="Base ATR multiplier"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show detailed output for each ticker"
    ),
    mock: bool = typer.Option(
        False,
        "--mock",
        help="Use simulated data (for testing/demo)"
    )
):
    """
    Analyze all tickers in your default watchlist.
    
    Configure the watchlist in config.py.
    """
    console.print(f"[bold]Analyzing watchlist:[/bold] {', '.join(DEFAULT_CONFIG.watchlist)}")
    console.print()
    
    if mock:
        data_provider = MockDataProvider(seed=42)
        console.print("[dim]Using simulated data (--mock mode)[/dim]\n")
    else:
        data_provider = YFinanceProvider()
    
    recommender = StopRecommender(data_provider=data_provider)
    
    with console.status("[bold green]Fetching data..."):
        recommendations = recommender.analyze_watchlist(
            base_multiplier=multiplier
        )
    
    if not recommendations:
        console.print("[red]No valid recommendations generated.[/red]")
        raise typer.Exit(1)
    
    console.print(create_summary_table(recommendations))
    
    if verbose:
        console.print()
        for rec in recommendations:
            console.print(create_recommendation_panel(rec))
            console.print()


@app.command()
def quick(
    ticker: str = typer.Argument(..., help="Stock ticker"),
):
    """
    Quick one-liner output for a single ticker.
    
    Example: python cli.py quick NVDA
    """
    recommender = StopRecommender()
    
    try:
        rec = recommender.analyze(ticker.upper())
        regime = rec.volatility_regime
        regime_str = regime.regime.upper() if regime else "?"
        
        console.print(
            f"[bold]{rec.ticker}[/bold]: "
            f"${rec.current_price:.2f} → "
            f"Stop [cyan]${rec.suggested_stop:.2f}[/cyan] "
            f"({rec.stop_distance_pct:.1f}%) | "
            f"ATR ${rec.atr_14:.2f} × {rec.regime_adjusted_multiplier:.1f} | "
            f"Vol: {regime_str}"
        )
    except DataProviderError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
