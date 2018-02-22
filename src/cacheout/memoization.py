"""The memoization modules provides standalone memoiziation decorators that
create an independent cache object for each decorated function.
"""

from .cache import Cache
from .fifo import FIFOCache
from .lfu import LFUCache
from .lifo import LIFOCache
from .lru import LRUCache
from .mru import MRUCache
from .rr import RRCache


def memoize(maxsize=128, ttl=0):
    """Decorator that wraps a function with a memoizing callable.

    A cache object will be created for each memoized function using
    :class:`.Cache` and the arguments provided to this decorator followed by an
    immediate call to :meth:`.Cache.memoize` to wrap the function. The cache
    object can be accessed at ``<function>.cache``. The uncached version
    (i.e. the original function) can be accessed at ``<function>.uncached``.
    Each return value from the function will be cached using the function
    arguments as the cache key.

    Args:
        maxsize (int, optional): Maximum size of cache dictionary. Defaults to
            ``128``.
        ttl (int, optional): Default TTL for all cache entries. Defaults to
            ``0`` which means that entries do not expire.
    """
    return Cache(maxsize=maxsize, ttl=ttl).memoize()


def fifo_memoize(maxsize=128, ttl=0):
    """Like :func:`memoize` except it uses :class:`.FIFOCache`."""
    return FIFOCache(maxsize=maxsize, ttl=ttl).memoize()


def lifo_memoize(maxsize=128, ttl=0):
    """Like :func:`memoize` except it uses :class:`.LIFOCache`."""
    return LIFOCache(maxsize=maxsize, ttl=ttl).memoize()


def lfu_memoize(maxsize=128, ttl=0):
    """Like :func:`memoize` except it uses :class:`.LFUCache`."""
    return LFUCache(maxsize=maxsize, ttl=ttl).memoize()


def lru_memoize(maxsize=128, ttl=0):
    """Like :func:`memoize` except it uses :class:`.LRUCache`."""
    return LRUCache(maxsize=maxsize, ttl=ttl).memoize()


def mru_memoize(maxsize=128, ttl=0):
    """Like :func:`memoize` except it uses :class:`.MRUCache`."""
    return MRUCache(maxsize=maxsize, ttl=ttl).memoize()


def rr_memoize(maxsize=128, ttl=0):
    """Like :func:`memoize` except it uses :class:`.RRCache`."""
    return RRCache(maxsize=maxsize, ttl=ttl).memoize()
