import pytest

from cacheout import Cache


@pytest.mark.parametrize("typed_first", [False, True])
def test_memoize_modes_do_not_confuse_literal_tuples_with_type_tags(typed_first):
    cache = Cache()
    calls = []

    def target(value):
        calls.append(value)
        return type(value).__name__, value

    typed = cache.memoize(typed=True)(target)
    untyped = cache.memoize()(target)
    operations = [(typed, 1, ("int", 1)), (untyped, (int, 1), ("tuple", (int, 1)))]
    if not typed_first:
        operations.reverse()
    for function, value, expected in operations:
        assert function(value) == expected
        assert function(value) == expected
    assert len(calls) == 2
    assert typed.cache_key(1) != untyped.cache_key((int, 1))
    assert typed.invalidate() == 2
    assert len(cache) == 0


@pytest.mark.parametrize("typed", [False, True])
def test_wrappers_with_the_same_mode_still_share_entries(typed):
    cache = Cache()

    def target(value):
        return object()

    first = cache.memoize(typed=typed)(target)
    second = cache.memoize(typed=typed)(target)
    assert first(1) is second(1)
    assert first.cache_key(1) == second.cache_key(1)


@pytest.mark.asyncio
async def test_async_memoize_modes_keep_distinct_results():
    cache = Cache()

    async def target(value):
        return type(value).__name__, value

    typed = cache.memoize(typed=True)(target)
    untyped = cache.memoize()(target)
    assert await typed(1) == ("int", 1)
    assert await untyped((int, 1)) == ("tuple", (int, 1))
