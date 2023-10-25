import pytest

from cacheout import Cache


@pytest.fixture
def cache() -> Cache:
    cache = Cache(maxsize=2, enable_stats=True)
    cache.add("1", "one")
    cache.add("2", "two")
    cache.add("3", "three")
    return cache


def test_info(cache: Cache):
    """Test that cache.stats.info() gets statistics."""
    assert cache.get("1") is None
    assert cache.get("2") == "two"

    stats = cache.stats.info()
    assert stats is not None
    assert stats.hits == 1
    assert stats.misses == 4
    assert stats.hit_rate == 0.2
    assert stats.accesses == 5
    assert stats.miss_rate == 0.8
    assert stats.eviction_rate == 0.2
    assert stats.total_entries == 2
    assert repr(stats) == (
        "Stats("
        "hits=1, misses=4, total_entries=2, accesses=5, "
        "hit_rate=0.2, miss_rate=0.8, eviction_rate=0.2"
        ")"
    )


def test_reset(cache: Cache):
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
    assert stats.total_entries == 0


def test_pause(cache: Cache):
    """Test that cache.stats.pause() pauses statistics."""
    assert cache.get("1") is None
    assert cache.get("2") == "two"

    stats = cache.stats.info()
    assert stats is not None
    assert stats.hits == 1
    assert stats.misses == 4
    assert stats.hit_rate == 0.2
    assert stats.accesses == 5
    assert stats.miss_rate == 0.8
    assert stats.eviction_rate == 0.2
    assert stats.total_entries == 2

    cache.stats.pause()
    assert cache.stats.is_paused() is True

    assert cache.get("1") is None
    assert cache.get("2") == "two"
    cache.add("4", "four")

    stats = cache.stats.info()
    assert stats is not None
    assert stats.hits == 1
    assert stats.misses == 4
    assert stats.hit_rate == 0.2
    assert stats.accesses == 5
    assert stats.miss_rate == 0.8
    assert stats.eviction_rate == 0.2
    assert stats.total_entries == 2


def test_resume(cache: Cache):
    """Test that cache.stats.resume() resumes statistics."""
    cache.stats.pause()
    assert cache.stats.is_paused() is True

    cache.stats.resume()
    assert cache.stats.is_paused() is False

    assert cache.get("1") is None
    assert cache.get("2") == "two"

    stats = cache.stats.info()
    assert stats is not None
    assert stats.hits == 1
    assert stats.misses == 4
    assert stats.hit_rate == 0.2
    assert stats.accesses == 5
    assert stats.miss_rate == 0.8
    assert stats.eviction_rate == 0.2
    assert stats.total_entries == 2


def test_disable(cache: Cache):
    """Test that cache.stats.pause() disables statistics."""
    cache.stats.disable()
    assert cache.stats.is_enabled() is False

    stats = cache.stats.info()
    assert stats is not None
    assert stats.hits == 0
    assert stats.misses == 0
    assert stats.accesses == 0
    assert stats.hit_rate == 1.0
    assert stats.miss_rate == 0.0
    assert stats.eviction_rate == 1.0
    assert stats.total_entries == 0


def test_enable(cache: Cache):
    """Test that cache.stats.pause() enables statistics."""
    cache.stats.disable()
    assert cache.stats.is_enabled() is False

    cache.stats.enable()
    assert cache.stats.is_enabled() is True

    assert cache.get("1") is None
    assert cache.get("2") == "two"
    cache.add("4", "four")
    cache.add("5", "five")

    stats = cache.stats.info()
    assert stats is not None
    assert stats.hits == 1
    assert stats.misses == 3
    assert stats.accesses == 4
    assert stats.hit_rate == 0.25
    assert stats.miss_rate == 0.75
    assert stats.eviction_rate == 0.5
    assert stats.total_entries == 2
