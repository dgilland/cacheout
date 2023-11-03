import pytest

from cacheout import Cache


@pytest.fixture
def cache() -> Cache:
    cache = Cache(maxsize=2)
    cache.stats.enable()
    cache.add("1", "one")
    cache.add("2", "two")
    cache.add("3", "three")
    return cache


def test_stats_tracker_repr(cache: Cache):
    """Test that stats tracker has expected repr."""
    assert repr(cache.stats) == f"CacheStatsTracker(info={repr(cache.stats.info())})"


def test_stats_tracker_info(cache: Cache):
    """Test that cache.stats.info() gets statistics."""
    assert cache.get("1") is None
    assert cache.get("2") == "two"

    info = cache.stats.info()
    assert info is not None
    assert info.hits == 1
    assert info.misses == 4
    assert info.hit_rate == 0.2
    assert info.accesses == 5
    assert info.miss_rate == 0.8
    assert info.eviction_rate == 0.2
    assert info.total_entries == 2


def test_stats_tracker_info_asdict(cache: Cache):
    info = cache.stats.info()
    assert info.asdict() == {
        "hits": info.hits,
        "misses": info.misses,
        "evictions": info.evictions,
        "total_entries": info.total_entries,
        "accesses": info.accesses,
        "hit_rate": info.hit_rate,
        "miss_rate": info.miss_rate,
        "eviction_rate": info.eviction_rate,
    }


def test_stats_tracker_reset(cache: Cache):
    """Test that cache.stats.reset() clears statistics."""
    cache.stats.reset()

    stats = cache.stats.info()
    assert stats is not None
    assert stats.hits == 0
    assert stats.misses == 0
    assert stats.accesses == 0
    assert stats.hit_rate == 1.0
    assert stats.miss_rate == 0.0
    assert stats.eviction_rate == 1.0
    assert stats.total_entries == 2


def test_stats_tracker_pause(cache: Cache):
    """Test that cache.stats.pause() pauses statistics."""
    assert cache.get("1") is None
    assert cache.get("2") == "two"

    info = cache.stats.info()
    assert info is not None
    assert info.hits == 1
    assert info.misses == 4
    assert info.hit_rate == 0.2
    assert info.accesses == 5
    assert info.miss_rate == 0.8
    assert info.eviction_rate == 0.2
    assert info.total_entries == 2

    cache.stats.pause()
    assert cache.stats.is_paused() is True
    assert cache.stats.is_active() is False

    assert cache.get("1") is None
    assert cache.get("2") == "two"
    cache.add("4", "four")

    info = cache.stats.info()
    assert info is not None
    assert info.hits == 1
    assert info.misses == 4
    assert info.hit_rate == 0.2
    assert info.accesses == 5
    assert info.miss_rate == 0.8
    assert info.eviction_rate == 0.2
    assert info.total_entries == 2


def test_stats_tracker_resume(cache: Cache):
    """Test that cache.stats.resume() resumes statistics."""
    cache.stats.pause()
    assert cache.stats.is_paused() is True
    assert cache.stats.is_active() is False

    cache.stats.resume()
    assert cache.stats.is_paused() is False
    assert cache.stats.is_active() is True

    assert cache.get("1") is None
    assert cache.get("2") == "two"

    info = cache.stats.info()
    assert info is not None
    assert info.hits == 1
    assert info.misses == 4
    assert info.hit_rate == 0.2
    assert info.accesses == 5
    assert info.miss_rate == 0.8
    assert info.eviction_rate == 0.2
    assert info.total_entries == 2


def test_stats_tracker_disable(cache: Cache):
    """Test that cache.stats.pause() disables statistics."""
    cache.stats.disable()
    assert cache.stats.is_enabled() is False
    assert cache.stats.is_active() is False

    info = cache.stats.info()
    assert info is not None
    assert info.hits == 0
    assert info.misses == 0
    assert info.accesses == 0
    assert info.hit_rate == 1.0
    assert info.miss_rate == 0.0
    assert info.eviction_rate == 1.0
    assert info.total_entries == 2


def test_stats_tracker_enable(cache: Cache):
    """Test that cache.stats.pause() enables statistics."""
    cache.stats.disable()
    assert cache.stats.is_enabled() is False
    assert cache.stats.is_active() is False

    cache.stats.enable()
    assert cache.stats.is_enabled() is True
    assert cache.stats.is_active() is True

    assert cache.get("1") is None
    assert cache.get("2") == "two"
    cache.add("4", "four")
    cache.add("5", "five")

    info = cache.stats.info()
    assert info is not None
    assert info.hits == 1
    assert info.misses == 3
    assert info.accesses == 4
    assert info.hit_rate == 0.25
    assert info.miss_rate == 0.75
    assert info.eviction_rate == 0.5
    assert info.total_entries == 2
