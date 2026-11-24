import typing as t

import pytest

from cacheout import Cache


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
            mapping: dict = {}
            mapping["self"] = mapping
            return mapping
        items: list[t.Any] = []
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

    value: dict[str, t.Any] = {"label": "before"}
    value["self"] = value
    assert label(value) == "before"
    value["label"] = "after"
    assert label(value) == "after"
