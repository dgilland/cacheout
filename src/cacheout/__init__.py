"""Cacheout is a caching library for Python.
"""

from .__version__ import __version__

from .cache import Cache
from .fifo import FIFOCache
from .lifo import LIFOCache
from .lfu import LFUCache
from .lru import LRUCache
from .mru import MRUCache
from .rr import RRCache
from .memoization import (
    memoize,
    fifo_memoize,
    lfu_memoize,
    lifo_memoize,
    lru_memoize,
    mru_memoize,
    rr_memoize
)
from .manager import CacheManager
