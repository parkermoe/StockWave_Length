"""
Screener strategy registration system.

Provides a decorator-based plugin architecture for screener strategies.
"""
import sys
from pathlib import Path
from typing import Dict, Type, List, Optional, Tuple
import importlib
import pkgutil

sys.path.insert(0, str(Path(__file__).parent.parent))
from screeners.base_screener import ScreenerStrategy


# Global registry of screener strategies
SCREENER_REGISTRY: Dict[str, Type[ScreenerStrategy]] = {}


def register_screener(name: Optional[str] = None, description: Optional[str] = None):
    """
    Decorator to register a screener strategy.
    
    Usage:
        @register_screener(name="my_screener", description="My custom screener")
        class MyScreener(ScreenerStrategy):
            ...
    
    Args:
        name: Optional name override (uses class.get_name() if not provided)
        description: Optional description override
    """
    def decorator(cls: Type[ScreenerStrategy]) -> Type[ScreenerStrategy]:
        # Instantiate to get name if not provided
        instance = cls()
        screener_name = name or instance.get_name()
        
        # Register in global registry
        SCREENER_REGISTRY[screener_name] = cls
        
        # Store metadata on class
        cls._screener_name = screener_name
        cls._screener_description = description or instance.get_description()
        
        return cls
    
    return decorator


def get_screener(name: str) -> Optional[ScreenerStrategy]:
    """
    Get a screener instance by name.
    
    Args:
        name: Screener name (e.g., 'canslim', 'mark_minervini')
        
    Returns:
        Instance of the screener, or None if not found
    """
    screener_class = SCREENER_REGISTRY.get(name)
    if screener_class:
        return screener_class()
    return None


def list_screeners() -> List[str]:
    """
    Get list of all registered screener names.
    
    Returns:
        List of screener names
    """
    return list(SCREENER_REGISTRY.keys())


def get_screener_info(name: str) -> Optional[Dict[str, any]]:
    """
    Get detailed information about a screener.
    
    Args:
        name: Screener name
        
    Returns:
        Dict with name, description, and criteria, or None if not found
    """
    screener = get_screener(name)
    if not screener:
        return None
    
    return {
        "name": screener.get_name(),
        "description": screener.get_description(),
        "criteria": screener.get_criteria(),
        "config": screener.get_config()
    }


def get_all_screeners_info() -> List[Dict[str, any]]:
    """
    Get information about all registered screeners.
    
    Returns:
        List of dicts with screener information
    """
    return [get_screener_info(name) for name in list_screeners()]


def auto_discover_screeners():
    """
    Automatically discover and import all screener modules.
    
    Scans the screeners/ directory for *_screener.py files and imports them,
    triggering their @register_screener decorators.
    """
    import screeners
    
    # Get the screeners package path
    screeners_path = Path(screeners.__file__).parent
    
    # Import all *_screener.py modules
    for finder, name, ispkg in pkgutil.iter_modules([str(screeners_path)]):
        if name.endswith('_screener') and name not in ['base_screener']:
            try:
                importlib.import_module(f'screeners.{name}')
            except Exception as e:
                print(f"Warning: Failed to import screener module '{name}': {e}")
    
    # Also check custom/ subdirectory
    custom_path = screeners_path / 'custom'
    if custom_path.exists():
        for finder, name, ispkg in pkgutil.iter_modules([str(custom_path)]):
            if name.endswith('_screener'):
                try:
                    importlib.import_module(f'screeners.custom.{name}')
                except Exception as e:
                    print(f"Warning: Failed to import custom screener '{name}': {e}")
