"""The rr module provides the :class:`RRCache` (Random Replacement) class."""

from random import SystemRandom
import typing as t

from .cache import Cache


random = SystemRandom()


class RRCache(Cache):
    """The Random Replacment (RR) cache is like :class:`.Cache` but uses a random eviction policy
    where keys are evicted in a random order."""

    def __next__(self) -> t.Hashable:
        with self._lock:
            try:
                return random.choice(list(self._cache.keys()))
            except IndexError:  # pragma: no cover
                raise StopIteration
