import pytest

from cacheout import Cache, LFUCache, RemovalCause


@pytest.mark.parametrize("cache_type", [Cache, LFUCache])
@pytest.mark.parametrize("operation", ["evict", "set"])
@pytest.mark.parametrize("error_type", [KeyError, StopIteration, ValueError])
def test_capacity_eviction_propagates_callback_errors(cache_type, operation, error_type):
    cache = cache_type(maxsize=2, enable_stats=True)
    cache.set("first", 1)
    cache.set("second", 2)
    error = error_type("delete callback failed")
    removals = []

    def fail(key, value, cause):
        removals.append((key, value, cause))
        raise error

    cache.on_delete = fail
    with pytest.raises(error_type) as raised:
        if operation == "evict":
            cache.configure(maxsize=1)
            cache.evict()
        else:
            cache.set("new", 3)

    assert raised.value is error
    assert removals == [("first", 1, RemovalCause.FULL)]
    assert dict(cache.items()) == {"second": 2}
    assert cache.stats.info().eviction_count == 1

    cache.on_delete = None
    cache.set("recovered", 4)
    assert cache.get("recovered") == 4
