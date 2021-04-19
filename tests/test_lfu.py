import pytest

from cacheout import LFUCache


parametrize = pytest.mark.parametrize


@pytest.fixture
def cache() -> LFUCache:
    return LFUCache(maxsize=5)


def test_lfu_eviction(cache: LFUCache):
    """Test that LFUCache evicts least frequently used set entries first."""
    key_counts = [("a", 4), ("b", 3), ("c", 5), ("d", 1), ("e", 2)]

    for key, count in key_counts:
        cache.set(key, key)

        for _ in range(count):
            cache.get(key)

    sorted_key_counts = sorted(key_counts, key=lambda kc: kc[1])
    eviction_order = [kc[0] for kc in sorted_key_counts]
    max_access_count = max([kc[1] for kc in sorted_key_counts])

    for n in range(len(key_counts)):
        cache.set(n, n)

        for _ in range(max_access_count + 1):
            cache.get(n)

        assert cache.full()
        assert eviction_order[n] not in cache

        for key in eviction_order[(n + 1) :]:
            assert key in cache


def test_lfu_get(cache: LFUCache):
    """Test that LFUCache.get() returns cached value."""
    for key, value in cache.items():
        assert cache.get(key) == value


def test_lfu_clear(cache: LFUCache):
    """Test that LFUCache.clear() resets access counts."""
    cache.maxsize = 2

    cache.set(1, 1)
    cache.set(2, 2)

    for _ in range(5):
        cache.get(1)

    cache.set(3, 3)

    assert 2 not in cache

    cache.clear()
    assert len(cache) == 0

    cache.set(1, 1)
    cache.set(2, 2)

    cache.get(2)
    cache.set(3, 3)

    assert 1 not in cache


def test_lfu_maxsize_violation_regression():
    """Test that LFUCache doesn't allow maxsize violation."""
    cache = LFUCache(maxsize=4)

    for _ in range(4):
        cache.add(1, 1)
        cache.add(2, 1)

    for _ in range(3):
        cache.add(3, 1)
        cache.add(4, 1)

    cache.add(5, 1)
    cache.add(6, 1)

    assert list(cache.keys()) == [1, 2, 4, 6]


def test_lfu_has_does_not_increase_access_count(cache: LFUCache):
    """Test that LFUCache.has does not increase access counts to keys."""
    assert not cache.has("a")
    assert not cache._access_counts

    cache.set("a", True)
    assert cache._access_counts["a"] == -1

    assert cache.has("a")
    assert cache._access_counts["a"] == -1


def test_lfu_contains_does_not_increase_access_count(cache: LFUCache):
    """Test that "key in LFUCache" does not increase access counts to keys."""
    assert "a" not in cache
    assert not cache._access_counts

    cache.set("a", True)
    assert cache._access_counts["a"] == -1

    assert "a" in cache
    assert cache._access_counts["a"] == -1


def test_lfu_access_count_using_default_callable():
    cache = LFUCache(default=lambda key: False)
    value = cache.get("a")

    assert value is False
    assert cache._access_counts["a"] == -1
