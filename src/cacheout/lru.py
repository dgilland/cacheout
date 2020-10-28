"""The lru module provides the :class:`LRUCache` (Least Recently Used) class."""

from .cache import Cache


class LRUCache(Cache):
    """
    Like :class:`.Cache` but uses a least-recently-used eviction policy.

    The primary difference with :class:`.Cache` is that cache entries are moved to the end of the
    eviction queue when both :meth:`get` and :meth:`set` are called (as opposed to :class:`.Cache`
    that only moves entries on ``set()``.
    """

    def _get(self, key, default=None):
        value = super()._get(key, default=default)

        if key in self._cache:
            self._cache.move_to_end(key)

        return value
