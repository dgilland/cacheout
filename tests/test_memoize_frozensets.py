from decimal import Decimal

import pytest

from cacheout import Cache


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("nested", [False, True])
def test_frozenset_element_types_participate_in_typed_keys(typed, nested):
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


def test_frozensets_recursively_preserve_tuple_element_types():
    cache = Cache()

    @cache.memoize(typed=True)
    def identity(value):
        return value

    left, right = frozenset([(1,)]), frozenset([(1.0,)])
    assert identity.cache_key(left) != identity.cache_key(right)
    assert identity(left) is left
    assert identity(right) is right
