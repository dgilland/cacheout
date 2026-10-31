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


@pytest.mark.parametrize(
    "cache_type", [Cache, FIFOCache, LFUCache, LIFOCache, LRUCache, MRUCache, RRCache]
)
@pytest.mark.parametrize("error_type", [ValueError, KeyError])
def test_delete_callback_error_keeps_bookkeeping_consistent(cache_type, error_type):
    cache = cache_type(timer=lambda: 0, enable_stats=True)
    cache.set("key", "old", ttl=1)
    error = error_type("callback failed")

    def fail(key, value, cause):
        assert (key, value, cause) == ("key", "old", RemovalCause.DELETE)
        raise error

    cache.on_delete = fail
    with pytest.raises(error_type) as caught:
        cache.delete("key")
    assert caught.value is error
    assert cache.copy() == {}
    assert cache.expire_times() == {}
    cache.on_delete = None
    cache.set("new", "value")
    assert cache.popitem() == ("new", "value")


@pytest.mark.parametrize(
    "cache_type", [Cache, FIFOCache, LFUCache, LIFOCache, LRUCache, MRUCache, RRCache]
)
def test_delete_callback_can_replace_key_with_its_own_ttl(cache_type):
    now = [0]
    cache = cache_type(timer=lambda: now[0])
    cache.set("key", "old", ttl=1)

    def replace(key, value, cause):
        assert cache.expire_times() == {}
        cache.set(key, "new", ttl=5)

    cache.on_delete = replace
    assert cache.delete("key") == 1
    assert cache.expire_times() == {"key": 5}
    assert cache.get("key") == "new"
    cache.on_delete = None
    now[0] = 5
    assert cache.delete_expired() == 1
    assert cache.copy() == {}
