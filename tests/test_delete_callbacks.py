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


@pytest.mark.parametrize(
    "cache_type", [Cache, FIFOCache, LFUCache, LIFOCache, LRUCache, MRUCache, RRCache]
)
@pytest.mark.parametrize("replacement_ttl", [0, 5])
def test_expiration_sweep_preserves_other_key_refreshed_by_callback(cache_type, replacement_ttl):
    now = [0]
    cache = cache_type(timer=lambda: now[0])
    cache.set("first", "old first", ttl=1)
    cache.set("second", "old second", ttl=1)
    removals = []

    def replace_other(key, value, cause):
        removals.append((key, value, cause))
        if key == "first":
            cache.set("second", "fresh second", ttl=replacement_ttl)

    cache.on_delete = replace_other
    now[0] = 1
    assert cache.delete_expired() == 1
    assert cache.copy() == {"second": "fresh second"}
    assert removals == [("first", "old first", RemovalCause.EXPIRED)]
    assert cache.expire_times() == ({"second": 6} if replacement_ttl else {})
    if isinstance(cache, LFUCache):
        assert cache._access_counts == {"second": -1}

    now[0] = 6
    assert cache.delete_expired() == (1 if replacement_ttl else 0)
    assert cache.copy() == ({} if replacement_ttl else {"second": "fresh second"})


@pytest.mark.parametrize(
    "cache_type", [Cache, FIFOCache, LFUCache, LIFOCache, LRUCache, MRUCache, RRCache]
)
def test_expiration_sweep_does_not_count_other_key_deleted_by_callback(cache_type):
    now = [0]
    cache = cache_type(timer=lambda: now[0])
    cache.set("first", 1, ttl=1)
    cache.set("second", 2, ttl=1)

    def delete_other(key, value, cause):
        if key == "first":
            assert cache.delete("second") == 1

    cache.on_delete = delete_other
    now[0] = 1
    assert cache.delete_expired() == 1
    assert cache.copy() == {}
    assert cache.expire_times() == {}
