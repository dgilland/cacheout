
from random import SystemRandom

import pytest

from cacheout import RRCache


parametrize = pytest.mark.parametrize
random = SystemRandom()


@pytest.fixture
def cache():
    _cache = RRCache(maxsize=10)
    for n in range(_cache.maxsize):
        _cache.set(n, n)
    assert _cache.full()
    return _cache


def test_rr_random_eviction(cache):
    """Test that RRCache randomly removes cache items."""


def assert_keys_evicted_in_random_order(cache, keys):
    """Assert that cache keys are evicted in the same order as `keys`."""
    cache_keys = keys.copy()
    evicted_keys = []

    for n in range(cache.maxsize, cache.maxsize * 2):
        cache.set(n, n)
        assert cache.full()

        evicted_key = list(set(cache_keys + [n]).difference(cache.keys()))[0]
        evicted_keys.append(evicted_key)
        cache_keys.remove(evicted_key)
        cache_keys.append(n)

    assert keys != evicted_keys
    assert reversed(keys) != evicted_keys


def test_rr_set_eviction(cache):
    """Test that RRCache evicts randomly set entries first."""
    keys = random.sample(list(cache.keys()), len(cache))

    for key in keys:
        cache.set(key, key)

    assert_keys_evicted_in_random_order(cache, keys)


def test_rr_get_eviction(cache):
    """Test that RRCache evicts randomly accessed entries first."""
    keys = random.sample(list(cache.keys()), len(cache))

    for key in keys:
        cache.get(key)

    assert_keys_evicted_in_random_order(cache, keys)


def test_rr_get_set_eviction(cache):
    """Test that RRCache evicts randomly set/accessed entries first."""
    all_keys = list(cache.keys())
    get_keys = random.sample(all_keys, len(cache) // 2)
    set_keys = random.sample(set(all_keys).difference(get_keys),
                             len(cache) // 2)

    assert not set(get_keys).intersection(set_keys)
    assert set(get_keys + set_keys) == set(all_keys)

    for key in get_keys:
        cache.get(key)

    for key in set_keys:
        cache.set(key, key)

    keys = get_keys + set_keys

    assert_keys_evicted_in_random_order(cache, keys)


def test_rr_get(cache):
    """Test that RRCache.get() returns cached value."""
    for key, value in cache.items():
        assert cache.get(key) == value
