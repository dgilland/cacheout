"""Cacheout is a caching library for Python."""

__version__ = "0.16.0"

from .cache import UNSET, Cache, RemovalCause
from .fifo import FIFOCache
from .lfu import LFUCache
from .lifo import LIFOCache
from .lru import LRUCache
from .manager import CacheManager
from .memoization import (
    fifo_memoize,
    lfu_memoize,
    lifo_memoize,
    lru_memoize,
    memoize,
    mru_memoize,
    rr_memoize,
)
from .mru import MRUCache
from .rr import RRCache
from .stats import CacheStats, CacheStatsTracker
