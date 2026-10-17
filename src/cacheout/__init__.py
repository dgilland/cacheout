"""Cacheout is a caching library for Python."""

__version__ = "0.17.0"

from .cache import UNSET as UNSET, Cache as Cache, RemovalCause as RemovalCause
from .fifo import FIFOCache as FIFOCache
from .lfu import LFUCache as LFUCache
from .lifo import LIFOCache as LIFOCache
from .lru import LRUCache as LRUCache
from .manager import CacheManager as CacheManager
from .memoization import (
    fifo_memoize as fifo_memoize,
    lfu_memoize as lfu_memoize,
    lifo_memoize as lifo_memoize,
    lru_memoize as lru_memoize,
    memoize as memoize,
    mru_memoize as mru_memoize,
    rr_memoize as rr_memoize,
)
from .mru import MRUCache as MRUCache
from .rr import RRCache as RRCache
from .stats import CacheStats as CacheStats, CacheStatsTracker as CacheStatsTracker
