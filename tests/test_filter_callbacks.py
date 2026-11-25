import pytest

from cacheout import Cache, LRUCache, MRUCache


@pytest.mark.parametrize("cache_class", [LRUCache, MRUCache])
@pytest.mark.parametrize("operation", ["get_many", "delete_many"])
def test_filter_can_read_values_from_ordered_cache(cache_class, operation):
    cache = cache_class()
    cache.set_many({"one": 1, "two": 2, "three": 3})
    result = getattr(cache, operation)(lambda key: cache.get(key) >= 2)
    if operation == "get_many":
        assert result == {"two": 2, "three": 3}
        assert len(cache) == 3
    else:
        assert result == 2
        assert cache.copy() == {"one": 1}


def test_filter_does_not_visit_keys_added_by_callback():
    cache = Cache()
    cache.set_many({"one": 1, "two": 2})
    visited = []

    def matches(key):
        visited.append(key)
        cache.set("new", 3)
        return True

    assert cache.get_many(matches) == {"one": 1, "two": 2}
    assert visited == ["one", "two"]
    assert cache.get("new") == 3


def test_filter_tolerates_deletion_by_callback():
    cache = Cache()
    cache.set_many({"one": 1, "two": 2})

    def matches(key):
        cache.delete(key)
        return True

    assert cache.get_many(matches) == {}
    assert len(cache) == 0
