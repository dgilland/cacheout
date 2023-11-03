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
        hit_count: The number of cache hits.
        miss_count: The number of cache misses.
        eviction_count: The number of cache entries have been evicted.
        entry_count: The total number of cache entries.
    """

    hit_count: int = 0
    miss_count: int = 0
    eviction_count: int = 0
    entry_count: int = 0

    @property
    def access_count(self) -> int:
        """The number of times cache has been accessed."""
        return self.hit_count + self.miss_count

    @property
    def hit_rate(self) -> float:
        """The cache hit rate."""
        if self.access_count == 0:
            return 0.0
        return self.hit_count / self.access_count

    @property
    def miss_rate(self) -> float:
        """The cache miss rate."""
        if self.access_count == 0:
            return 0.0
        return self.miss_count / self.access_count

    @property
    def eviction_rate(self) -> float:
        """The cache eviction rate."""
        if self.access_count == 0:
            return 0.0
        return self.eviction_count / self.access_count

    def __repr__(self):
        data = self.to_dict()
        fields = []
        for k, v in data.items():
            if isinstance(v, float):
                s = f"{v:0.2f}"
            else:
                s = f"{v!r}"
            fields.append(f"{k}={s}")
        return f"{self.__class__.__name__}({', '.join(fields)})"

    def __iter__(self):
        return iter(self.to_dict().items())

    def to_dict(self) -> t.Dict[str, t.Any]:
        """Return dictionary representation of object."""
        return {
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "eviction_count": self.eviction_count,
            "entry_count": self.entry_count,
            "access_count": self.access_count,
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

    def inc_hit_count(self, count: int = 1) -> None:
        """Increment the number of cache hits."""
        if not self._enabled or self._paused:
            return

        with self._lock:
            self._stats.hit_count += count

    def inc_miss_count(self, count: int = 1) -> None:
        """Increment the number of cache misses."""
        if not self._enabled or self._paused:
            return

        with self._lock:
            self._stats.miss_count += count

    def inc_eviction_count(self, count: int = 1) -> None:
        """Increment the number of cache evictions."""
        if not self._enabled or self._paused:
            return

        with self._lock:
            self._stats.eviction_count += count

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
        """Return whether statistics tracking is enabled."""
        return self._enabled

    def is_paused(self) -> bool:
        """Return whether statistics tracking is paused."""
        return self._paused

    def is_active(self) -> bool:
        """Return whether statistics tracking is active (enabled and not paused)."""
        return self._enabled and not self._paused

    def reset(self) -> None:
        """Reset statistics to zero values."""
        with self._lock:
            self._stats = CacheStats()

    def info(self) -> CacheStats:
        """Return a snapshot of the cache statistics."""
        with self._lock:
            self._stats.entry_count = len(self._cache)
            return self._stats.copy()
