"""Cacheout is a caching library for Python.
"""

from .__pkg__ import (
    __description__,
    __url__,
    __version__,
    __author__,
    __email__,
    __license__
)

from .cache import Cache
from .manager import CacheManager
from .lru import LRUCache
