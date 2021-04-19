"""The lru module provides the :class:`LRUCache` (Least Recently Used) class."""

import typing as t

from .cache import Cache


class LRUCache(Cache):
    """
    Like :class:`.Cache` but uses a least-recently-used eviction policy.

    The primary difference with :class:`.Cache` is that cache entries are moved to the end of the
    eviction queue when both :meth:`get` and :meth:`set` are called (as opposed to :class:`.Cache`
    that only moves entries on ``set()``.
    """

    def get(self, key: t.Hashable, default: t.Any = None) -> t.Any:
        with self._lock:
            value = super().get(key, default=default)
            if key in self._cache:
                self._cache.move_to_end(key)
            return value

    get.__doc__ = Cache.get.__doc__
