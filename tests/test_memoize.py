from collections import OrderedDict
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


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("method, args", [("count", (1,)), ("__len__", ())])
def test_memoize_invalidate_shared_native_method_entries(typed, method, args):
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


def test_memoize_invalidate_native_method_clears_both_typing_modes():
    cache = Cache()
    values = [1]
    untyped = cache.memoize()(values.count)
    typed = cache.memoize(typed=True)(values.count)
    assert untyped(1) == typed(1) == 1
    assert len(cache) == 2
    assert typed.invalidate() == 2
    assert len(cache) == 0


def test_memoize_invalidate_shared_native_class_method_entries():
    cache = Cache()
    first = cache.memoize()(dict.fromkeys)
    second = cache.memoize()(dict.fromkeys)
    assert first(["a"]) == {"a": None}
    assert second.invalidate() == 1
    assert len(cache) == 0


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("kind", ["writable", "format", "unhashable_owner"])
def test_memoize_unhashable_memoryview_uses_identity(typed, kind):
    calls = []

    @Cache().memoize(typed=typed)
    def describe(view):
        calls.append(view)
        return view.format, len(view), view.tobytes()

    def make_view():
        if kind == "writable":
            return memoryview(bytearray(b"abcd"))
        if kind == "format":
            return memoryview(b"abcd").cast("H")
        return memoryview(bytearray(b"abcd")).toreadonly()

    first, second = make_view(), make_view()
    expected = describe.uncached(first)
    calls.clear()
    assert describe(first) == expected
    assert describe(first) == expected
    assert describe(second) == expected
    assert len(calls) == 2
    assert describe.cache_key(first) != describe.cache_key(second)
    assert describe.invalidate() == 2


@pytest.mark.parametrize("typed", [False, True])
def test_memoize_hashable_memoryviews_still_share_equal_keys(typed):
    calls = []

    @Cache().memoize(typed=typed)
    def length(view):
        calls.append(view)
        return len(view)

    first, second = memoryview(b"abc"), memoryview(b"abc")
    assert length(first) == length(second) == 3
    assert len(calls) == 1
    assert length.cache_key(first) == length.cache_key(second)


def test_memoize_does_not_hide_value_errors_from_custom_hashes():
    error = ValueError("broken custom hash")

    class BrokenHash:
        def __hash__(self):
            raise error

    @Cache().memoize()
    def identity(value):
        pytest.fail("The original hash failure should propagate before calling the function")

    with pytest.raises(ValueError) as raised:
        identity(BrokenHash())
    assert raised.value is error


@pytest.mark.parametrize("typed", [False, True])
def test_memoize_distinguishes_unequal_ordered_mappings(typed):
    calls = []

    @Cache().memoize(typed=typed)
    def keys(mapping):
        calls.append(mapping)
        return tuple(mapping)

    first = OrderedDict([("a", 1), ("b", 2)])
    second = OrderedDict(reversed(list(first.items())))
    assert first != second
    assert keys(first) == ("a", "b")
    assert keys(second) == ("b", "a")
    assert keys(OrderedDict(first)) == ("a", "b")
    assert len(calls) == 2
    assert keys.invalidate() == 2


@pytest.mark.parametrize("typed", [False, True])
def test_memoize_copies_ordered_mapping_order(typed):
    @Cache().memoize(typed=typed)
    def keys(mapping):
        return tuple(mapping)

    mapping = OrderedDict([("a", 1), ("b", 2)])
    assert keys(mapping) == ("a", "b")
    mapping.move_to_end("a")
    assert keys(mapping) == ("b", "a")
    mapping.move_to_end("b")
    assert keys(mapping) == ("a", "b")


@pytest.mark.parametrize("typed", [False, True])
def test_memoize_preserves_nested_ordered_mappings(typed):
    @Cache().memoize(typed=typed)
    def keys(value):
        return tuple(value["items"][0])

    first = OrderedDict([("a", [1]), ("b", [2])])
    second = OrderedDict(reversed(list(first.items())))
    assert keys({"items": [first]}) == ("a", "b")
    assert keys({"items": [second]}) == ("b", "a")


@pytest.mark.parametrize("typed", [False, True])
def test_memoize_ordered_mapping_values_keep_type_and_cycle_handling(typed):
    @Cache().memoize(typed=typed)
    def identity(value):
        return value

    integer = OrderedDict([("value", [1])])
    floating = OrderedDict([("value", [1.0])])
    assert (identity.cache_key(integer) != identity.cache_key(floating)) is typed

    recursive = OrderedDict()
    recursive["self"] = recursive
    assert identity(recursive) is recursive
    assert identity(recursive) is recursive

    # Normal dictionaries retain their existing order-insensitive keys.
    assert identity.cache_key({"a": 1, "b": 2}) == identity.cache_key({"b": 2, "a": 1})


def test_memoized_method_binding_and_helpers():
    cache = Cache()

    class Service:
        @cache.memoize()
        def load(self, value: int, /, *, label: str) -> str:
            return f"{label}: {value}"

    service = Service()
    assert service.load(1, label="item") == "item: 1"
    assert Service.load(service, 1, label="item") == "item: 1"
    assert service.load.uncached(service, 1, label="item") == "item: 1"
    assert service.load.cache_key(service, 1, label="item") in cache
    assert service.load.invalidate() == 1
