"""The lfu module provides the :class:`LFUCache` (Least Frequently Used) class."""

from collections import Counter

from .cache import Cache


class LFUCache(Cache):
    """
    The Least Frequently Used (LFU) cache is like :class:`.Cache` but uses a least-frequently-used
    eviction policy.

    The primary difference with :class:`.Cache` is that access to cache entries (i.e. calls to
    :meth:`get` and :meth:`set`) are tracked; each call to :meth:`get` will increment the cache
    key's access count while calls to :meth:`set` will reset the counter. During cache eviction, the
    entry with the lowest access count is removed first.
    """

    def setup(self):
        super().setup()
        self._access_counts = Counter()

    def __next__(self):
        with self._lock:
            try:
                return self._access_counts.most_common(1)[0][0]
            except ValueError:  # pragma: no cover
                # Empty cache.
                raise StopIteration

    def _touch(self, key):
        # Decrement access counts so we can use Counter.most_common() to return the least accessed
        # keys first (i.e. keys with a higher count).
        self._access_counts[key] -= 1

    def _get(self, key, default=None):
        value = super()._get(key, default=default)
        if key in self:
            self._touch(key)
        return value

    def _set(self, key, value, ttl=None):
        super()._set(key, value, ttl=ttl)
        self._touch(key)

    def _delete(self, key):
        count = super()._delete(key)

        try:
            del self._access_counts[key]
        except KeyError:  # pragma: no cover
            pass

        return count

    def _clear(self):
        super()._clear()
        self._access_counts.clear()
