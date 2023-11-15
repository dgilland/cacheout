"""The lfu module provides the :class:`LFUCache` (Least Frequently Used) class."""

from collections import Counter
import typing as t

from .cache import T_TTL, Cache, RemovalCause


class LFUCache(Cache):
    """
    The Least Frequently Used (LFU) cache is like :class:`.Cache` but uses a least-frequently-used
    eviction policy.

    The primary difference with :class:`.Cache` is that access to cache entries (i.e. calls to
    :meth:`get` and :meth:`set`) are tracked; each call to :meth:`get` will increment the cache
    key's access count while calls to :meth:`set` will reset the counter. During cache eviction, the
    entry with the lowest access count is removed first.
    """

    _access_counts: Counter

    def setup(self) -> None:
        super().setup()
        self._access_counts: Counter = Counter()

    def __next__(self) -> t.Hashable:
        with self._lock:
            try:
                return self._access_counts.most_common(n=1)[0][0]
            except (ValueError, IndexError):  # pragma: no cover
                # Empty cache.
                raise StopIteration

    def _touch(self, key: t.Hashable) -> None:
        # Decrement access counts so we can use Counter.most_common() to return the least accessed
        # keys first (i.e. keys with a higher count).
        self._access_counts[key] -= 1

    def get(self, key: t.Hashable, default: t.Any = None) -> t.Any:
        with self._lock:
            value = super().get(key, default=default)
            if key in self._cache:
                self._touch(key)
            return value

    get.__doc__ = Cache.get.__doc__

    def set(self, key: t.Hashable, value: t.Any, ttl: t.Optional[T_TTL] = None) -> None:
        with self._lock:
            super().set(key, value, ttl=ttl)
            self._touch(key)

    set.__doc__ = Cache.set.__doc__

    def add(self, key: t.Hashable, value: t.Any, ttl: t.Optional[T_TTL] = None) -> None:
        with self._lock:
            super().add(key, value, ttl=ttl)
            self._touch(key)

    add.__doc__ = Cache.add.__doc__

    def _delete(self, key: t.Hashable, cause: t.Optional[RemovalCause] = None) -> int:
        count = super()._delete(key, cause)

        try:
            del self._access_counts[key]
        except KeyError:  # pragma: no cover
            pass

        return count

    def _clear(self) -> None:
        super()._clear()
        self._access_counts.clear()
