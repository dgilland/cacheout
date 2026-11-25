import pytest

from cacheout import Cache


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("method, args", [("count", (1,)), ("__len__", ())])
def test_invalidate_shared_native_method_entries(typed, method, args):
    cache = Cache()
    values, other_values = [1], [1]
    first = cache.memoize(typed=typed)(getattr(values, method))
    second = cache.memoize(typed=typed)(getattr(values, method))
    other_instance = cache.memoize(typed=typed)(getattr(other_values, method))
    other_method = cache.memoize(typed=typed)(values.index)
    cache.set(("unrelated", "entry"), "keep")

    assert first(*args) == 1
    assert second(*args) == 1
    assert other_instance(*args) == 1
    assert other_method(1) == 0
    assert len(cache) == 4

    values.append(1)
    assert second.invalidate() == 1
    assert second(*args) == 2
    assert first.invalidate() == 1
    assert len(cache) == 3
    assert cache.get(other_instance.cache_key(*args)) == 1
    assert cache.get(other_method.cache_key(1)) == 0
    assert cache.get(("unrelated", "entry")) == "keep"


def test_invalidate_native_method_clears_both_typing_modes():
    cache = Cache()
    values = [1]
    untyped = cache.memoize()(values.count)
    typed = cache.memoize(typed=True)(values.count)
    assert untyped(1) == typed(1) == 1
    assert len(cache) == 2
    assert typed.invalidate() == 2
    assert len(cache) == 0


def test_invalidate_shared_native_class_method_entries():
    cache = Cache()
    first = cache.memoize()(dict.fromkeys)
    second = cache.memoize()(dict.fromkeys)
    assert first(["a"]) == {"a": None}
    assert second.invalidate() == 1
    assert len(cache) == 0
