"""
Stock screening strategies module.

Provides various screening strategies for identifying trading candidates.
Uses a plugin-based registry system for easy extensibility.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from screeners.base_screener import ScreenerStrategy, ScreenerResult
from screeners.registry import (
    register_screener,
    get_screener,
    list_screeners,
    get_screener_info,
    get_all_screeners_info,
    auto_discover_screeners
)
from screeners.screener_manager import ScreenerManager, ScreenOutput, ScreenSummary

# Auto-discover and register all screeners
auto_discover_screeners()

__all__ = [
    'ScreenerStrategy',
    'ScreenerResult',
    'register_screener',
    'get_screener',
    'list_screeners',
    'get_screener_info',
    'get_all_screeners_info',
    'auto_discover_screeners',
    'ScreenerManager',
    'ScreenOutput',
    'ScreenSummary'
]
