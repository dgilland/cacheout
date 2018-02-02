"""The rr module provides the :class:`RRCache` (Random Replacement) class.
"""

from contextlib import suppress
from random import SystemRandom

from .cache import Cache


random = SystemRandom()


class RRCache(Cache):
    """The Random Replacment (RR) cache is like :class:`.Cache` but uses a
    random eviction policy where keys are evicted in a random order.
    """
    def __next__(self):
        with self._lock:
            try:
                return random.choice(list(self._cache.keys()))
            except IndexError:  # pragma: no cover
                raise StopIteration
