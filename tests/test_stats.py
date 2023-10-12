import pytest

from cacheout import Cache


@pytest.fixture
def cache() -> Cache:
    return Cache(maxsize=2, stats=True)


def test_stats(cache: Cache):
    """Test that cache.stats() gets statistics."""
    cache.add("1", "one")
    cache.add("2", "two")
    cache.add("3", "three")

    assert cache.get("1") is None
    assert cache.get("2") == "two"

    stats = cache.get_stats()
    assert stats is not None
    assert stats.hits == 1
    assert stats.misses == 1
    assert stats.hit_rate == 0.5
    assert stats.access == 2
    assert stats.miss_rate == 0.5
    assert stats.eviction_rate == 0.5
    assert stats.total == 2
    assert repr(stats) == (
        "Stats("
        "hits:1, misses:1, total:2, access:2, hit_rate:0.5, miss_rate:0.5, eviction_rate:0.5"
        ")"
    )

    cache.clear()
    stats = cache.get_stats()
    assert stats is not None
    assert stats.hits == 0
    assert stats.misses == 0
    assert stats.access == 0
    assert stats.hit_rate == 1.0
    assert stats.miss_rate == 0.0
    assert stats.eviction_rate == 1.0
    assert stats.total == 0
    assert repr(stats) == (
        "Stats("
        "hits:0, misses:0, total:0, access:0, hit_rate:1.0, miss_rate:0.0, eviction_rate:1.0"
        ")"
    )
