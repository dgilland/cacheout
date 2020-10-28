"""The mru module provides the :class:`MRUCache` (Most Recently Used) class."""

from .lru import LRUCache


class MRUCache(LRUCache):
    """
    The Most Recently Used (MRU) cache is like :class:`.Cache` and :class:`.LRUCache` but uses a
    most-recently-used replacement policy.

    The primary difference with :class:`.Cache` is that cache entries are moved to the end of the
    eviction queue when both :meth:`get` and :meth:`set` are called (as opposed to :class:`.Cache`
    that only moves entries on ``set()``.

    The primary difference with :class:`.LRUCache` is that cache entries are evicted from the end of
    the eviction queue first instead of evicting from the beginning.
    """

    def __next__(self):
        return next(reversed(self._cache))
