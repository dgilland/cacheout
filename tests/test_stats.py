from threading import Event, RLock, Thread

import pytest

from cacheout import Cache


@pytest.fixture
def cache() -> Cache:
    cache = Cache(maxsize=2)
    cache.stats.enable()
    cache.add("a", 1)
    cache.add("b", 2)
    cache.add("c", 3)
    return cache


def test_stats_tracker_repr(cache: Cache):
    """Test that stats tracker has expected repr."""
    assert repr(cache.stats) == f"CacheStatsTracker(info={repr(cache.stats.info())})"


def test_stats_tracker_info(cache: Cache):
    """Test that cache.stats.info() gets statistics."""
    assert cache.get("a") is None
    assert cache.get("b") == 2

    info = cache.stats.info()
    assert info is not None
    assert info.hit_count == 1
    assert info.miss_count == 4
    assert info.hit_rate == 0.2
    assert info.access_count == 5
    assert info.miss_rate == 0.8
    assert info.eviction_rate == 0.2
    assert info.entry_count == 2


def test_stats_tracker_info_does_not_invert_cache_lock(monkeypatch):
    # 2026-10-11: Coordinate both lock acquisitions without leaving blocked threads behind.
    cache_locked = Event()
    reading_length = Event()
    errors = []
    snapshots = []

    class CoordinatedCache(Cache):
        def __len__(self):
            reading_length.set()
            return super().__len__()

    class BoundedLock:
        def __init__(self):
            self.lock = RLock()

        def __enter__(self):
            if not self.lock.acquire(timeout=5):
                raise TimeoutError("statistics lock blocked by the snapshot")
            return self

        def __exit__(self, *args):
            self.lock.release()

    cache = CoordinatedCache(enable_stats=True)
    cache.set("key", "value")
    reading_length.clear()
    monkeypatch.setattr(cache.stats, "_lock", BoundedLock())

    def get_value():
        try:
            with cache._lock:
                cache_locked.set()
                assert reading_length.wait(5)
                assert cache.get("key") == "value"
        except Exception as exc:
            errors.append(exc)

    def get_info():
        try:
            snapshots.append(cache.stats.info())
        except Exception as exc:
            errors.append(exc)

    getter = Thread(target=get_value, daemon=True)
    getter.start()
    assert cache_locked.wait(5)
    reader = Thread(target=get_info, daemon=True)
    reader.start()
    getter.join(6)
    reader.join(6)
    assert not getter.is_alive()
    assert not reader.is_alive()
    assert errors == []
    assert len(snapshots) == 1
    assert snapshots[0].hit_count == 1
    assert snapshots[0].entry_count == 1


def test_stats_tracker_info_to_dict(cache: Cache):
    info = cache.stats.info()
    expected = {
        "hit_count": info.hit_count,
        "miss_count": info.miss_count,
        "eviction_count": info.eviction_count,
        "entry_count": info.entry_count,
        "access_count": info.access_count,
        "hit_rate": info.hit_rate,
        "miss_rate": info.miss_rate,
        "eviction_rate": info.eviction_rate,
    }
    assert info.to_dict() == expected
    assert dict(info) == expected


def test_stats_tracker_reset(cache: Cache):
    """Test that cache.stats.reset() clears statistics."""
    cache.stats.reset()

    info = cache.stats.info()
    assert info is not None
    assert info.hit_count == 0
    assert info.miss_count == 0
    assert info.access_count == 0
    assert info.hit_rate == 0.0
    assert info.miss_rate == 0.0
    assert info.eviction_rate == 0.0
    assert info.entry_count == 2


def test_stats_tracker_pause(cache: Cache):
    """Test that cache.stats.pause() pauses statistics."""
    assert cache.get("a") is None
    assert cache.get("b") == 2

    info = cache.stats.info()
    assert info is not None
    assert info.hit_count == 1
    assert info.miss_count == 4
    assert info.hit_rate == 0.2
    assert info.access_count == 5
    assert info.miss_rate == 0.8
    assert info.eviction_rate == 0.2
    assert info.entry_count == 2

    cache.stats.pause()
    assert cache.stats.is_paused() is True
    assert cache.stats.is_active() is False

    assert cache.get("a") is None
    assert cache.get("b") == 2
    cache.add("d", 4)

    info = cache.stats.info()
    assert info is not None
    assert info.hit_count == 1
    assert info.miss_count == 4
    assert info.hit_rate == 0.2
    assert info.access_count == 5
    assert info.miss_rate == 0.8
    assert info.eviction_rate == 0.2
    assert info.entry_count == 2


def test_stats_tracker_resume(cache: Cache):
    """Test that cache.stats.resume() resumes statistics."""
    cache.stats.pause()
    assert cache.stats.is_paused() is True
    assert cache.stats.is_active() is False

    cache.stats.resume()
    assert cache.stats.is_paused() is False
    assert cache.stats.is_active() is True

    assert cache.get("a") is None
    assert cache.get("b") == 2

    info = cache.stats.info()
    assert info is not None
    assert info.hit_count == 1
    assert info.miss_count == 4
    assert info.hit_rate == 0.2
    assert info.access_count == 5
    assert info.miss_rate == 0.8
    assert info.eviction_rate == 0.2
    assert info.entry_count == 2


def test_stats_tracker_disable(cache: Cache):
    """Test that cache.stats.pause() disables statistics."""
    cache.stats.disable()
    assert cache.stats.is_enabled() is False
    assert cache.stats.is_active() is False

    info = cache.stats.info()
    assert info is not None
    assert info.hit_count == 0
    assert info.miss_count == 0
    assert info.access_count == 0
    assert info.hit_rate == 0.0
    assert info.miss_rate == 0.0
    assert info.eviction_rate == 0.0
    assert info.entry_count == 2


def test_stats_tracker_enable(cache: Cache):
    """Test that cache.stats.pause() enables statistics."""
    cache.stats.disable()
    assert cache.stats.is_enabled() is False
    assert cache.stats.is_active() is False

    cache.stats.enable()
    assert cache.stats.is_enabled() is True
    assert cache.stats.is_active() is True

    assert cache.get("a") is None
    assert cache.get("b") == 2
    cache.add("d", 4)
    cache.add("e", 5)

    info = cache.stats.info()
    assert info is not None
    assert info.hit_count == 1
    assert info.miss_count == 3
    assert info.access_count == 4
    assert info.hit_rate == 0.25
    assert info.miss_rate == 0.75
    assert info.eviction_rate == 0.5
    assert info.entry_count == 2
