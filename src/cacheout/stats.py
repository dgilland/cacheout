from threading import RLock


class Stats:
    """An object to represent a snapshot of statistics."""

    def __init__(self, hits: int, misses: int, evictions: int, total: int) -> None:
        self._hits = hits
        self._misses = misses
        self._evictions = evictions
        self._total = total

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
        return self._total

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

    def __init__(self) -> None:
        self._lock = RLock()

        self._hit_count = 0
        self._miss_count = 0
        self._evicted_count = 0
        self._total_count = 0

        self._enabled = True
        self._paused = False

    def _inc_hits(self, count: int) -> None:
        if not self._enabled or self._paused:
            return

        with self._lock:
            self._hit_count += count

    def _inc_misses(self, count: int) -> None:
        if not self._enabled or self._paused:
            return

        with self._lock:
            self._miss_count += count

    def _inc_evictions(self, count: int) -> None:
        if not self._enabled or self._paused:
            return

        with self._lock:
            self._evicted_count += count

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
            self._hit_count = 0
            self._miss_count = 0
            self._evicted_count = 0
            self._total_count = 0

    def info(self) -> Stats:
        """Get a snapshot of statistics."""
        return Stats(
            hits=self._hit_count,
            misses=self._miss_count,
            evictions=self._evicted_count,
            total=self._total_count,
        )
