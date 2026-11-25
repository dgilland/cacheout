import pytest

from cacheout import Cache


def test_memoize_builtin_without_signature():
    cache = Cache(enable_stats=True)
    maximum = cache.memoize()(max)
    assert maximum(2, 7) == 7
    assert maximum(2, 7) == 7
    assert maximum([3, 1], key=abs) == 3
    assert maximum([], default=9) == 9
    assert maximum.uncached is max
    assert cache.get(maximum.cache_key(2, 7)) == 7
    assert maximum.invalidate() == 3
    assert len(cache) == 0


def test_memoize_builtin_failures_are_not_cached():
    cache = Cache()
    maximum = cache.memoize()(max)
    with pytest.raises(TypeError):
        maximum()
    with pytest.raises(TypeError):
        maximum(1, 2, unknown=True)
    assert len(cache) == 0
    assert maximum(1, 2) == 2


def test_memoize_builtin_keeps_typed_keys():
    maximum = Cache().memoize(typed=True)(max)
    assert type(maximum(1, 2)) is int
    assert type(maximum(1.0, 2.0)) is float
    assert maximum.cache_key(1, 2) != maximum.cache_key(1.0, 2.0)
