import pytest

from cacheout import (
    Cache,
    FIFOCache,
    LFUCache,
    LIFOCache,
    LRUCache,
    MRUCache,
    RemovalCause,
    RRCache,
)


CACHE_TYPES = [Cache, FIFOCache, LFUCache, LIFOCache, LRUCache, MRUCache, RRCache]


@pytest.mark.parametrize("cache_type", CACHE_TYPES)
@pytest.mark.parametrize("operation", ["get", "has", "add"])
def test_expiration_callback_key_error_propagates(cache_type, operation):
    now = [0]
    cache = cache_type(timer=lambda: now[0], enable_stats=True)
    cache.set("key", "old", ttl=1)
    error = KeyError("callback configuration missing")
    defaults = []
    reads = []
    removals = []

    def default(key):
        defaults.append(key)
        return "default"

    def fail(key, value, cause):
        removals.append((key, value, cause))
        raise error

    cache.default = default
    cache.on_get = lambda *args: reads.append(args)
    cache.on_delete = fail
    now[0] = 1
    with pytest.raises(KeyError) as caught:
        if operation == "get":
            cache.get("key")
        elif operation == "has":
            cache.has("key")
        else:
            cache.add("key", "new")

    assert caught.value is error
    assert removals == [("key", "old", RemovalCause.EXPIRED)]
    assert defaults == []
    assert reads == []
    assert cache.copy() == {}
    assert cache.expire_times() == {}
    assert cache.stats.info().access_count == 0
    if isinstance(cache, LFUCache):
        assert cache._access_counts == {}

    cache.on_delete = None
    cache.set("recovered", "value")
    assert cache.popitem() == ("recovered", "value")


@pytest.mark.parametrize("cache_type", CACHE_TYPES)
def test_expiration_callback_key_error_preserves_replacement(cache_type):
    now = [0]
    cache = cache_type(timer=lambda: now[0], enable_stats=True)
    cache.set("key", "old", ttl=1)
    error = KeyError("callback failed after replacement")
    defaults = []

    def replace_and_fail(key, value, cause):
        cache.set(key, "replacement", ttl=5)
        raise error

    cache.on_delete = replace_and_fail
    now[0] = 1
    with pytest.raises(KeyError) as caught:
        cache.get("key", default=defaults.append)
    assert caught.value is error
    assert defaults == []
    assert cache.copy() == {"key": "replacement"}
    assert cache.expire_times() == {"key": 6}
    assert cache.stats.info().access_count == 0
    if isinstance(cache, LFUCache):
        assert cache._access_counts == {"key": -1}
    cache.on_delete = None
    assert cache.get("key") == "replacement"


@pytest.mark.parametrize("cache_type", CACHE_TYPES)
def test_timer_key_error_propagates_without_replacing_cached_value(cache_type):
    cache = cache_type(timer=lambda: 0, enable_stats=True)
    cache.set("key", "old", ttl=5)
    error = KeyError("clock configuration missing")
    defaults = []
    reads = []

    def fail():
        raise error

    cache.configure(timer=fail)
    cache.on_get = lambda *args: reads.append(args)
    with pytest.raises(KeyError) as caught:
        cache.get("key", default=defaults.append)
    assert caught.value is error
    assert defaults == []
    assert reads == []
    assert cache.copy() == {"key": "old"}
    assert cache.expire_times() == {"key": 5}
    assert cache.stats.info().access_count == 0
    if isinstance(cache, LFUCache):
        assert cache._access_counts == {"key": -1}


@pytest.mark.parametrize("cache_type", CACHE_TYPES)
def test_ordinary_expiration_still_runs_default_and_records_miss(cache_type):
    now = [0]
    cache = cache_type(timer=lambda: now[0], enable_stats=True)
    cache.set("key", "old", ttl=1)
    removals = []
    reads = []
    cache.on_delete = lambda *args: removals.append(args)
    cache.on_get = lambda *args: reads.append(args)
    now[0] = 1
    assert cache.get("key", default=lambda key: "new") == "new"
    assert removals == [("key", "old", RemovalCause.EXPIRED)]
    assert reads == [("key", "new", False)]
    assert cache.copy() == {"key": "new"}
    assert cache.expire_times() == {}
    assert cache.stats.info().miss_count == 1
    assert cache.get("key") == "new"
    assert cache.stats.info().hit_count == 1
