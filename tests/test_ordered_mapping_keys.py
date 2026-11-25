from collections import OrderedDict

import pytest

from cacheout import Cache


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
