import copy
from threading import RLock
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .cache import Cache  # pragma: no cover


class Stats:
    """
    An object to represent a snapshot of statistics.

    Attributes:
        _hits: The number of cache hits.
        _misses: The number of cache misses.
        _evictions: The number of cache entries have been evicted.
        _total_entries: The total number of cache entries.
    """

    def __init__(
        self, hits: int = 0, misses: int = 0, evictions: int = 0, total_entries: int = 0
    ) -> None:
        self._hits = hits
        self._misses = misses
        self._evictions = evictions
        self._total_entries = total_entries

    @property
    def hits(self) -> int:
        """The number of cache hits."""
        return self._hits

    @property
    def misses(self) -> int:
        """The number of cache misses."""
        return self._misses

    @property
    def total_entries(self) -> int:
        """The total number of cache entries."""
        return self._total_entries

    @property
    def accesses(self) -> int:
        """The number of times cache has been accessed."""
        return self._hits + self._misses

    @property
    def hit_rate(self) -> float:
        """
        The cache hit rate.

        Return 1.0 when ``accesses`` == 0.
        """
        if self.accesses == 0:
            return 1.0
        return self.hits / self.accesses

    @property
    def miss_rate(self) -> float:
        """
        The cache miss rate.

        Return 0.0 when ``accesses`` == 0.
        """
        if self.accesses == 0:
            return 0.0
        return self.misses / self.accesses

    @property
    def eviction_rate(self) -> float:
        """
        The cache eviction rate.

        Return 1.0 when ``accesses`` == 0.
        """
        if self.accesses == 0:
            return 1.0
        return self._evictions / self.accesses

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            "("
            f"hits={self.hits}, misses={self.misses}, "
            f"total_entries={self.total_entries}, accesses={self.accesses}, "
            f"hit_rate={self.hit_rate}, miss_rate={self.miss_rate}, "
            f"eviction_rate={self.eviction_rate}"
            ")"
        )


class StatsTracker:
    """
    An object to track statistics.

    Attributes:
        _hit_count: The number of cache hits.
        _miss_count: The number of cache misses.
        _evicted_count: The number of cache entries have been evicted.
        _total_count: The total number of cache entries.
        _enabled: A flag that indicates if statistics is enabled.
        _paused: A flag that indicates if statistics is paused.
    """

    _lock: RLock

    def __init__(self, cache: "Cache") -> None:
        self._cache = cache

        self._lock = RLock()
        self._stats = Stats()

        self._enabled = False
        self._paused = False

    def inc_hits(self, count: int) -> None:
        if not self._enabled or self._paused:
            return

        with self._lock:
            self._stats._hits += count

    def inc_misses(self, count: int) -> None:
        if not self._enabled or self._paused:
            return

        with self._lock:
            self._stats._misses += count

    def inc_evictions(self, count: int) -> None:
        if not self._enabled or self._paused:
            return

        with self._lock:
            self._stats._evictions += count

    def enable(self) -> None:
        """Enable statistics."""
        with self._lock:
            self._enabled = True

    def disable(self) -> None:
        """Disable statistics."""
        with self._lock:
            self.reset()
            self._enabled = False

    def is_enabled(self) -> bool:
        """Whether statistics is enabled."""
        return self._enabled

    def pause(self) -> None:
        """Pause statistics."""
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        """Resume statistics."""
        with self._lock:
            self._paused = False

    def is_paused(self) -> bool:
        """Whether statistics is paused."""
        return self._paused

    def reset(self) -> None:
        """Clear statistics."""
        with self._lock:
            self._stats = Stats()

    def info(self) -> Stats:
        """Get a snapshot of statistics."""
        with self._lock:
            self._stats._total_entries = len(self._cache)
            return copy.copy(self._stats)
