from decimal import Decimal
import typing as t
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
    fifo_memoize,
    lfu_memoize,
    lifo_memoize,
    lru_memoize,
    memoize,
    mru_memoize,
    rr_memoize,
)


parametrize = pytest.mark.parametrize


@parametrize(
    "memoizer,cache_class",
    [
        (memoize, Cache),
        (fifo_memoize, FIFOCache),
        (lfu_memoize, LFUCache),
        (lifo_memoize, LIFOCache),
        (lru_memoize, LRUCache),
        (mru_memoize, MRUCache),
        (rr_memoize, RRCache),
    ],
)
def test_memoize_cache(memoizer: t.Callable, cache_class: t.Type[Cache]):
    @memoizer()
    def func():
        pass

    assert isinstance(func.cache, cache_class)

    @memoizer(maxsize=None)
    def unbounded(value: int) -> int:
        return value

    for value in range(300):
        assert unbounded(value) == value
    assert len(unbounded.cache) == 300
    assert not unbounded.cache.full()

    patch = f"cacheout.memoization.{cache_class.__name__}"

    with mock.patch(patch) as mocked:

        @memoizer()
        def func2():
            pass

        assert mocked.called
        assert mocked().memoize.called


def test_memoize_bound_method_wrappers_can_invalidate_their_shared_entries():
    cache = Cache()

    class Service:
        def load(self, value):
            return value

    service, other = Service(), Service()
    first = cache.memoize()(service.load)
    second = cache.memoize()(service.load)
    unrelated = cache.memoize()(other.load)
    assert first(1) == 1
    assert second(2) == 2
    assert unrelated(3) == 3
    assert second.invalidate() == 2
    assert list(cache.values()) == [3]


def test_memoize_other_methods_on_the_same_instance_keep_their_entries():
    cache = Cache()

    class Service:
        def load(self, value):
            return value

        def save(self, value):
            return value

    service = Service()
    first = cache.memoize()(service.load)
    second = cache.memoize()(service.load)
    other = cache.memoize()(service.save)
    first(1)
    other(2)
    assert second.invalidate() == 1
    assert list(cache.values()) == [2]


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


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("kind", ["list", "dict", "tuple"])
def test_memoize_cyclic_container(typed, kind):
    calls = []

    @Cache().memoize(typed=typed)
    def identify(value):
        calls.append(value)
        return len(calls)

    def make_cycle():
        if kind == "dict":
            mapping = {}
            mapping["self"] = mapping
            return mapping
        items = []
        value = (items,) if kind == "tuple" else items
        items.append(value)
        return value

    first = make_cycle()
    second = make_cycle()
    assert identify(first) == 1
    assert identify(first) == 1
    assert identify(second) == 2
    assert identify(first) == 1
    assert identify.invalidate() == 2
    assert identify(first) == 3


def test_memoize_shared_children_still_use_structural_keys():
    @Cache().memoize()
    def identify(value):
        return object()

    child = [1, 2]
    assert identify([child, child]) is identify([[1, 2], [1, 2]])


def test_memoize_cycle_retains_noncyclic_fields():
    @Cache().memoize()
    def label(value):
        return value["label"]

    value = {"label": "before"}
    value["self"] = value
    assert label(value) == "before"
    value["label"] = "after"
    assert label(value) == "after"


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("nested", [False, True])
def test_memoize_frozenset_element_types_participate_in_typed_keys(typed, nested):
    cache = Cache()

    @cache.memoize(typed=typed)
    def identity(value):
        return value

    values = [frozenset([value]) for value in (1, 1.0, Decimal(1))]
    if nested:
        values = [({"items": value},) for value in values]
    keys = [identity.cache_key(value) for value in values]
    assert len(set(keys)) == (3 if typed else 1)
    if typed:
        for value in values:
            assert identity(value) is value


def test_memoize_frozensets_recursively_preserve_tuple_element_types():
    cache = Cache()

    @cache.memoize(typed=True)
    def identity(value):
        return value

    left, right = frozenset([(1,)]), frozenset([(1.0,)])
    assert identity.cache_key(left) != identity.cache_key(right)
    assert identity(left) is left
    assert identity(right) is right


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
def test_memoize_wrappers_with_the_same_mode_still_share_entries(typed):
    cache = Cache()

    def target(value):
        return object()

    first = cache.memoize(typed=typed)(target)
    second = cache.memoize(typed=typed)(target)
    assert first(1) is second(1)
    assert first.cache_key(1) == second.cache_key(1)


@pytest.mark.asyncio
async def test_memoize_async_modes_keep_distinct_results():
    cache = Cache()

    async def target(value):
        return type(value).__name__, value

    typed = cache.memoize(typed=True)(target)
    untyped = cache.memoize()(target)
    assert await typed(1) == ("int", 1)
    assert await untyped((int, 1)) == ("tuple", (int, 1))
