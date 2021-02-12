from random import SystemRandom

import pytest

from cacheout import MRUCache


parametrize = pytest.mark.parametrize
random = SystemRandom()


@pytest.fixture
def cache() -> MRUCache:
    _cache = MRUCache(maxsize=10)
    for n in range(_cache.maxsize):
        _cache.set(n, n)
    assert _cache.full()
    return _cache


def assert_keys_evicted_in_reverse_order(cache: MRUCache, keys: list):
    """Assert that cache keys are evicted in the reverse order as `keys`."""
    keys = keys.copy()
    for n in range(cache.maxsize, cache.maxsize * 2):
        cache.set(n, n)
        assert cache.full()
        assert keys.pop() not in cache

        if keys:
            next_key = keys[-1]
            assert next_key in cache
            cache.get(next_key)


def test_mru_set_eviction(cache: MRUCache):
    """Test that MRUCache evicts most recently set entries first."""
    keys = random.sample(list(cache.keys()), len(cache))

    for key in keys:
        cache.set(key, key)

    assert_keys_evicted_in_reverse_order(cache, keys)


def test_mru_get_eviction(cache: MRUCache):
    """Test that MRUCache evicts most recently accessed entries first."""
    keys = random.sample(list(cache.keys()), len(cache))

    for key in keys:
        cache.get(key)

    assert_keys_evicted_in_reverse_order(cache, keys)


def test_mru_get_set_eviction(cache: MRUCache):
    """Test that MRUCache evicts most recently set/accessed entries first."""
    all_keys = list(cache.keys())
    get_keys = random.sample(all_keys, len(cache) // 2)
    set_keys = random.sample(list(set(all_keys).difference(get_keys)), len(cache) // 2)

    assert not set(get_keys).intersection(set_keys)
    assert set(get_keys + set_keys) == set(all_keys)

    for key in get_keys:
        cache.get(key)

    for key in set_keys:
        cache.set(key, key)

    keys = get_keys + set_keys

    assert_keys_evicted_in_reverse_order(cache, keys)


def test_mru_get(cache: MRUCache):
    """Test that MRUCache.get() returns cached value."""
    for key, value in cache.items():
        assert cache.get(key) == value
