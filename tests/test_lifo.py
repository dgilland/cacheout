from random import SystemRandom

import pytest

from cacheout import LIFOCache


parametrize = pytest.mark.parametrize


@pytest.fixture
def cache():
    return LIFOCache(maxsize=5)


def test_lifo_eviction(cache):
    """Test that LIFOCache evicts entries added last first."""
    keys = list(range(1, cache.maxsize + 1))

    for key in keys:
        cache.set(key, key)

    assert cache.full()

    keys = sorted(keys, reverse=True)

    # NOTE: The below loop is a somewhat hacky way to test that the cache entries are
    # removed in LIFO order. It hinges on the reducing the cache maxsize as we go so
    # that the cache eviction will choose the next cache entry from the initial set.
    while keys:
        key = keys.pop(0)

        # Set here to evict "key". This will end up with "-key" added but we'll remove
        # by calling evict() below.
        cache.set(-key, -key)
        assert key not in cache

        # Since cache is full, this will remove 1 entry (the "-key" entry we just added.
        cache.evict()

        assert -key not in cache
        assert len(cache) == len(keys)

        # Decrement maxsize to make cache full again without having to modify cache
        # entries.
        cache.maxsize -= 1

        # Remaining keys should still be in cache.
        for key in keys:
            assert key in cache

    assert len(cache) == 0
