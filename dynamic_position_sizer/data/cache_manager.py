"""
Cache manager for storing and retrieving market data.

Implements file-based caching with TTL (time-to-live) support to reduce
API calls and improve performance.
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional, Dict
from dataclasses import dataclass, asdict
import hashlib

sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class CacheEntry:
    """Single cache entry with data and metadata."""
    data: Any
    timestamp: str  # ISO format datetime
    ttl_hours: int
    key: str
    
    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        cached_time = datetime.fromisoformat(self.timestamp)
        expiry_time = cached_time + timedelta(hours=self.ttl_hours)
        return datetime.now() > expiry_time
    
    def age_hours(self) -> float:
        """Get the age of this cache entry in hours."""
        cached_time = datetime.fromisoformat(self.timestamp)
        age = datetime.now() - cached_time
        return age.total_seconds() / 3600


class CacheManager:
    """
    Singleton cache manager for storing market data.
    
    Uses file-based JSON storage with automatic expiration handling.
    
    Usage:
        cache = CacheManager()
        cache.set('fundamentals:AAPL', data, ttl=24)
        data = cache.get('fundamentals:AAPL')
    """
    
    _instance = None
    
    def __new__(cls, cache_dir: Optional[Path] = None):
        """Singleton pattern - only one instance per process."""
        if cls._instance is None:
            cls._instance = super(CacheManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize the cache manager.
        
        Args:
            cache_dir: Directory for cache files (defaults to .cache/)
        """
        if self._initialized:
            return
        
        if cache_dir is None:
            # Default to .cache/ in project root
            project_root = Path(__file__).parent.parent
            cache_dir = project_root / '.cache'
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Stats tracking
        self.hits = 0
        self.misses = 0
        self.sets = 0
        
        self._initialized = True
        
        # Clean up expired entries on startup
        self.clear_expired()
    
    def _get_cache_file(self, key: str) -> Path:
        """Get the cache file path for a given key."""
        # Hash the key to create a safe filename
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.json"
    
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve data from cache.
        
        Args:
            key: Cache key (e.g., 'fundamentals:AAPL', 'universe:sp500')
            
        Returns:
            Cached data if found and not expired, None otherwise
        """
        cache_file = self._get_cache_file(key)
        
        if not cache_file.exists():
            self.misses += 1
            return None
        
        try:
            with open(cache_file, 'r') as f:
                entry_dict = json.load(f)
                entry = CacheEntry(**entry_dict)
            
            if entry.is_expired():
                # Remove expired entry
                cache_file.unlink()
                self.misses += 1
                return None
            
            self.hits += 1
            return entry.data
            
        except Exception as e:
            # Cache read error - treat as miss
            self.misses += 1
            return None
    
    def set(self, key: str, data: Any, ttl: int = 24) -> bool:
        """
        Store data in cache.
        
        Args:
            key: Cache key
            data: Data to cache (must be JSON-serializable)
            ttl: Time-to-live in hours (default 24)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            entry = CacheEntry(
                data=data,
                timestamp=datetime.now().isoformat(),
                ttl_hours=ttl,
                key=key
            )
            
            cache_file = self._get_cache_file(key)
            with open(cache_file, 'w') as f:
                json.dump(asdict(entry), f, indent=2)
            
            self.sets += 1
            return True
            
        except Exception as e:
            print(f"Cache write error for key '{key}': {e}")
            return False
    
    def invalidate(self, key: str) -> bool:
        """
        Remove a specific cache entry.
        
        Args:
            key: Cache key to invalidate
            
        Returns:
            True if entry was removed, False if not found
        """
        cache_file = self._get_cache_file(key)
        if cache_file.exists():
            cache_file.unlink()
            return True
        return False
    
    def clear_expired(self) -> int:
        """
        Remove all expired cache entries.
        
        Returns:
            Number of entries removed
        """
        removed = 0
        
        for cache_file in self.cache_dir.glob('*.json'):
            try:
                with open(cache_file, 'r') as f:
                    entry_dict = json.load(f)
                    entry = CacheEntry(**entry_dict)
                
                if entry.is_expired():
                    cache_file.unlink()
                    removed += 1
                    
            except Exception:
                # If we can't read it, remove it
                cache_file.unlink()
                removed += 1
        
        return removed
    
    def clear_all(self) -> int:
        """
        Remove all cache entries.
        
        Returns:
            Number of entries removed
        """
        removed = 0
        for cache_file in self.cache_dir.glob('*.json'):
            cache_file.unlink()
            removed += 1
        return removed
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with hits, misses, hit rate, and total entries
        """
        total_entries = len(list(self.cache_dir.glob('*.json')))
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0.0
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "hit_rate": hit_rate,
            "total_entries": total_entries,
            "cache_dir": str(self.cache_dir)
        }
    
    def get_entry_info(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a cache entry without retrieving the data.
        
        Args:
            key: Cache key
            
        Returns:
            Dict with metadata or None if not found
        """
        cache_file = self._get_cache_file(key)
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                entry_dict = json.load(f)
                entry = CacheEntry(**entry_dict)
            
            return {
                "key": entry.key,
                "timestamp": entry.timestamp,
                "ttl_hours": entry.ttl_hours,
                "age_hours": entry.age_hours(),
                "is_expired": entry.is_expired(),
                "file_size_kb": cache_file.stat().st_size / 1024
            }
            
        except Exception:
            return None


# Global cache instance
_global_cache = None


def get_cache() -> CacheManager:
    """Get the global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = CacheManager()
    return _global_cache
