#!/usr/bin/env python3
"""
Quick demo of screener with analyst integration.
Shows the new table format with analyst columns.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from screeners.screener_manager import ScreenerManager
from data.universe_provider import CustomUniverseProvider
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

# Demo universe
tickers = ['NVDA', 'AAPL', 'TSLA', 'AMD', 'META', 'GOOGL', 'MSFT', 'AMZN', 'NFLX', 'COST']

console.print("\n[bold]Screener Demo: high_volatility with Analyst Integration[/bold]")
console.print(f"[dim]Test universe: {', '.join(tickers)}[/dim]\n")

manager = ScreenerManager(universe='sp500')
manager.universe_provider = CustomUniverseProvider(tickers)

with console.status("[bold green]Running screener..."):
    summary = manager.run_screen(
        strategy_names=['high_volatility'],
        max_results=10,
        calculate_positions=False
    )

# Summary panel
console.print(Panel(
    f"[bold]Screened:[/bold] {summary.total_universe} stocks\n"
    f"[bold]Passed:[/bold] {summary.passed_screener} candidates\n"
    f"[bold]Time:[/bold] {summary.execution_time_seconds:.1f}s",
    title="Screen Summary",
    border_style="green"
))
console.print()

# Results table (matching CLI format)
table = Table(
    title=f"Top {len(summary.results)} Results with Analyst Data",
    box=box.ROUNDED,
    show_header=True,
    header_style="bold cyan"
)

table.add_column("Ticker", style="bold")
table.add_column("Score", justify="right")
table.add_column("Base", justify="right", style="dim")
table.add_column("Mult", justify="right", style="magenta")
table.add_column("Target$", justify="right", style="green")
table.add_column("Upside%", justify="right", style="green")
table.add_column("Rec", justify="right", style="yellow")
table.add_column("Analysts", justify="right", style="dim")

for result in summary.results:
    analyst = result.analyst_score
    
    base_str = f"{result.base_score:.0f}" if result.base_score else "-"
    mult_str = f"{analyst.multiplier:.2f}x" if analyst else "1.00x"
    target_str = f"${analyst.target_upside_pct:+.0f}%" if (analyst and analyst.target_upside_pct is not None) else "-"
    upside_str = f"{analyst.target_upside_pct:+.1f}%" if (analyst and analyst.target_upside_pct is not None) else "-"
    rec_str = f"{analyst.recommendation_mean:.2f}" if (analyst and analyst.recommendation_mean) else "-"
    count_str = f"{analyst.analyst_count}" if (analyst and analyst.analyst_count) else "-"
    
    # Color code upside
    if analyst and analyst.target_upside_pct:
        if analyst.target_upside_pct > 20:
            upside_str = f"[green]{upside_str}[/green]"
        elif analyst.target_upside_pct < 0:
            upside_str = f"[red]{upside_str}[/red]"
    
    # Color code recommendation (1=Strong Buy, 5=Sell)
    if analyst and analyst.recommendation_mean:
        if analyst.recommendation_mean <= 2.0:
            rec_str = f"[green]{rec_str}[/green]"
        elif analyst.recommendation_mean >= 3.5:
            rec_str = f"[red]{rec_str}[/red]"
    
    table.add_row(
        result.ticker,
        f"{result.screener_result.score:.0f}",
        base_str,
        mult_str,
        target_str,
        upside_str,
        rec_str,
        count_str
    )

console.print(table)

console.print("\n[bold]Key:[/bold]")
console.print("  [dim]Base[/dim] = Screener score before analyst adjustment")
console.print("  [magenta]Mult[/magenta] = Analyst multiplier (0.8x - 1.2x)")
console.print("  [green]Target$[/green] = Analyst price target upside")
console.print("  [yellow]Rec[/yellow] = Recommendation mean (1=Strong Buy, 5=Sell)")
console.print()
