
from unittest import mock

import pytest

from cacheout import (
    Cache,
    FIFOCache,
    LFUCache,
    LIFOCache,
    LRUCache,
    MRUCache,
    RRCache,
    memoize,
    fifo_memoize,
    lfu_memoize,
    lifo_memoize,
    lru_memoize,
    mru_memoize,
    rr_memoize
)

parametrize = pytest.mark.parametrize


@parametrize('memoizer,cache_class', [
    (memoize, Cache),
    (fifo_memoize, FIFOCache),
    (lfu_memoize, LFUCache),
    (lifo_memoize, LIFOCache),
    (lru_memoize, LRUCache),
    (mru_memoize, MRUCache),
    (rr_memoize, RRCache),
])
def test_memoize_cache(memoizer, cache_class):
    @memoizer()
    def func():
        pass

    assert isinstance(func.cache, cache_class)

    patch = 'cacheout.memoization.{}'.format(cache_class.__name__)

    with mock.patch(patch) as mocked:
        @memoizer()
        def func():
            pass

        assert mocked.called
        assert mocked().memoize.called
