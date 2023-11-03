import dataclasses
from threading import RLock
import typing as t


if t.TYPE_CHECKING:
    from .cache import Cache  # pragma: no cover


@dataclasses.dataclass
class CacheStats:
    """
    Cache statistics snapshot.

    Attributes:
        hits: The number of cache hits.
        misses: The number of cache misses.
        evictions: The number of cache entries have been evicted.
        total_entries: The total number of cache entries.
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_entries: int = 0

    @property
    def accesses(self) -> int:
        """The number of times cache has been accessed."""
        return self.hits + self.misses

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
        return self.evictions / self.accesses

    def __repr__(self):
        """Return repr of object."""
        data = self.asdict()
        fields = []
        for k, v in data.items():
            if isinstance(v, float):
                s = f"{v:0.2f}"
            else:
                s = f"{v!r}"
            fields.append(f"{k}={s}")
        return f"{self.__class__.__name__}({', '.join(fields)})"

    def asdict(self) -> t.Dict[str, t.Any]:
        """Return dictionary representation of object."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total_entries": self.total_entries,
            "accesses": self.accesses,
            "hit_rate": self.hit_rate,
            "miss_rate": self.miss_rate,
            "eviction_rate": self.eviction_rate,
        }

    def copy(self):
        """Return copy of this object."""
        return dataclasses.replace(self)


class CacheStatsTracker:
    """Cache statistics tracker that manages cache stats."""

    _lock: RLock

    def __init__(self, cache: "Cache", *, enable: bool = True) -> None:
        self._cache = cache
        self._lock = RLock()
        self._stats = CacheStats()
        self._enabled = enable
        self._paused = False

    def __repr__(self):
        return f"{self.__class__.__name__}(info={self.info()})"

    def inc_hits(self, count: int) -> None:
        if not self._enabled or self._paused:
            return

        with self._lock:
            self._stats.hits += count

    def inc_misses(self, count: int) -> None:
        if not self._enabled or self._paused:
            return

        with self._lock:
            self._stats.misses += count

    def inc_evictions(self, count: int) -> None:
        if not self._enabled or self._paused:
            return

        with self._lock:
            self._stats.evictions += count

    def enable(self) -> None:
        """Enable statistics."""
        with self._lock:
            self._enabled = True

    def disable(self) -> None:
        """
        Disable statistics.

        Warning: This will reset all previously collected statistics.
        """
        with self._lock:
            self.reset()
            self._enabled = False

    def pause(self) -> None:
        """Pause statistics."""
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        """Resume statistics."""
        with self._lock:
            self._paused = False

    def is_enabled(self) -> bool:
        """Whether statistics tracking is enabled."""
        return self._enabled

    def is_paused(self) -> bool:
        """Whether statistics tracking is paused."""
        return self._paused

    def is_active(self) -> bool:
        """Whether statistics tracking is active (enabled and not paused)."""
        return self._enabled and not self._paused

    def reset(self) -> None:
        """Reset statistics."""
        with self._lock:
            self._stats = CacheStats()

    def info(self) -> CacheStats:
        """Get a snapshot of statistics."""
        with self._lock:
            self._stats.total_entries = len(self._cache)
            return self._stats.copy()
