"""Cacheout is a caching library for Python."""

__version__ = "0.14.1"

from .cache import Cache
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
