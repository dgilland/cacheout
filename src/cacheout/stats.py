from threading import RLock


class _StatsCounter:
    """
    An object to record statistics.

    Attributes:
        _hit_count: The number of cache hits.
        _miss_count: The number of cache misses.
        _evicted_count: The number of cache entries have been evicted.
        _total_count: The total number of cache entries.
    """

    _lock: RLock

    def __init__(self) -> None:
        self._lock = RLock()

        self._hit_count = 0
        self._miss_count = 0
        self._evicted_count = 0
        self._total_count = 0

    def record_hits(self, count: int) -> None:
        with self._lock:
            self._hit_count += count

    def record_misses(self, count: int) -> None:
        with self._lock:
            self._miss_count += count

    def record_evictions(self, count: int) -> None:
        with self._lock:
            self._evicted_count += count

    def record_total(self, count: int) -> None:
        with self._lock:
            self._total_count += count

    def reset(self) -> None:
        with self._lock:
            self._hit_count = 0
            self._miss_count = 0
            self._evicted_count = 0
            self._total_count = 0

    @property
    def hit_count(self) -> int:
        return self._hit_count

    @property
    def miss_count(self) -> int:
        return self._miss_count

    @property
    def evicted_count(self) -> int:
        return self._evicted_count

    @property
    def total_count(self) -> int:
        return self._total_count


class Stats:
    """An object to represent a snapshot of statistics."""

    def __init__(self, counter: _StatsCounter) -> None:
        self._hits = counter.hit_count
        self._misses = counter.miss_count
        self._evictions = counter.evicted_count
        self._total = counter.total_count

    @property
    def hits(self) -> int:
        """The number of cache hits."""
        return self._hits

    @property
    def misses(self) -> int:
        """The number of cache misses."""
        return self._misses

    @property
    def total(self) -> int:
        """The total number of cache entries."""
        return self._total

    @property
    def access(self) -> int:
        """The number of times cache has been accessed."""
        return self._hits + self._misses

    @property
    def hit_rate(self) -> float:
        """
        The cache hit rate.

        Return 1.0 when ``access_count`` == 0.
        """
        return 1.0 if self.access == 0 else self._hits / self.access

    @property
    def miss_rate(self) -> float:
        """
        The cache miss rate.

        Return 0.0 when ``access_count`` == 0.
        """
        return 0.0 if self.access == 0 else self._misses / self.access

    @property
    def eviction_rate(self) -> float:
        """
        The cache eviction rate.

        Return 1.0 when ``access_count`` == 0.
        """
        return 1.0 if self.access == 0 else self._evictions / self.access

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            "("
            f"hits:{self.hits}, misses:{self.misses}, "
            f"total:{self.total}, access:{self.access}, "
            f"hit_rate:{self.hit_rate}, miss_rate:{self.miss_rate}, "
            f"eviction_rate:{self.eviction_rate}"
            ")"
        )
