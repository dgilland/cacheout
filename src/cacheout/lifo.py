"""The lifo module provides the :class:`LIFOCache` (Last-In, First-Out) class.
"""

from .cache import Cache


class LIFOCache(Cache):
    """The Last-In, First-Out (LIFO) cache is like :class:`.Cache` but uses a
    last-in, first-out replacement policy.

    The primary difference with :class:`.Cache` is that cache entries are
    evicted from the end of the eviction queue first instead of evicting from
    the beginning, i.e., the last entry that was added to the cache is the
    first entry to be removed.
    """
    def __next__(self):
        return next(reversed(self._cache))
