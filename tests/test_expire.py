from decimal import Decimal, Overflow, localcontext
from unittest.mock import Mock

import pytest

from cacheout import (
    UNSET,
    Cache,
    FIFOCache,
    LFUCache,
    LIFOCache,
    LRUCache,
    MRUCache,
    RemovalCause,
    RRCache,
)


@pytest.mark.parametrize("original_ttl", [0, 10])
@pytest.mark.parametrize("ttl", [0, -1, 3, 20])
def test_expire_replaces_deadline(original_ttl, ttl):
    now = [0]
    cache = Cache(ttl=100, timer=lambda: now[0])
    value = []
    cache.set("key", value, ttl=original_ttl)
    now[0] = 2

    assert cache.expire("key", ttl) is True
    assert cache.copy()["key"] is value
    if ttl > 0:
        assert cache.expire_times() == {"key": 2 + ttl}
        assert not cache.expired("key", expires_on=2 + ttl - 0.5)
        assert cache.expired("key", expires_on=2 + ttl)
    else:
        assert cache.expire_times() == {}
        assert not cache.expired("key", expires_on=1000)


@pytest.mark.parametrize("value", [None, 0, False, "", UNSET])
def test_expire_accepts_existing_falsey_and_sentinel_values(value):
    cache = Cache(timer=lambda: 0)
    cache.set("key", value)
    assert cache.expire("key", 5) is True
    assert cache.copy()["key"] is value
    assert cache.expire_times() == {"key": 5}


@pytest.mark.parametrize(
    "cache_type", [Cache, FIFOCache, LFUCache, LIFOCache, LRUCache, MRUCache, RRCache]
)
def test_expire_preserves_replacement_policy_and_statistics(cache_type):
    cache = cache_type(maxsize=2, timer=lambda: 0, enable_stats=True)
    cache.set("first", "value")
    cache.set("second", "other")
    cache.get("first")
    cache.get("first")
    items = list(cache.items())
    stats = cache.stats.info()
    access_counts = cache._access_counts.copy() if isinstance(cache, LFUCache) else None
    cache.on_get = Mock()
    cache.on_set = Mock()
    cache.on_delete = Mock()

    assert cache.expire("first", 10) is True
    assert list(cache.items()) == items
    assert cache.stats.info() == stats
    assert cache.full()
    cache.on_get.assert_not_called()
    cache.on_set.assert_not_called()
    cache.on_delete.assert_not_called()
    if isinstance(cache, LFUCache):
        assert cache._access_counts == access_counts
        assert cache.popitem() == ("second", "other")


def test_expire_missing_key_does_not_load_a_default_or_call_timer():
    cache = Cache(default=Mock(), timer=Mock(side_effect=RuntimeError), enable_stats=True)
    assert cache.expire("missing", 5) is False
    assert cache.copy() == {}
    assert cache.expire_times() == {}
    assert cache.stats.info().access_count == 0
    cache.default.assert_not_called()
    cache.timer.assert_not_called()


@pytest.mark.parametrize(
    "cache_type", [Cache, FIFOCache, LFUCache, LIFOCache, LRUCache, MRUCache, RRCache]
)
@pytest.mark.parametrize("ttl", [0, 5])
def test_expire_does_not_revive_expired_entries(cache_type, ttl):
    now = [0]
    cache = cache_type(timer=lambda: now[0], enable_stats=True)
    cache.set("key", "value", ttl=1)
    cache.on_delete = Mock()
    now[0] = 1

    assert cache.expire("key", ttl) is False
    assert cache.copy() == {}
    assert cache.expire_times() == {}
    assert cache.stats.info().access_count == 0
    assert cache.stats.info().eviction_count == 0
    cache.on_delete.assert_called_once_with("key", "value", RemovalCause.EXPIRED)
    if isinstance(cache, LFUCache):
        assert not cache._access_counts


def test_expire_uses_one_timer_read():
    cache = Cache(timer=lambda: 0)
    cache.set("key", "value", ttl=5)
    timer = Mock(side_effect=[4, 100])
    cache.configure(timer=timer)

    assert cache.expire("key", 2) is True
    assert cache.expire_times() == {"key": 6}
    timer.assert_called_once_with()


def test_expire_failed_deadline_preserves_original_expiration():
    cache = Cache(timer=lambda: Decimal("9e9"))
    cache.set("key", "value", ttl=Decimal(20))
    original_items = cache.copy()
    original_expirations = cache.expire_times()

    with localcontext() as context:
        context.Emax = 9
        context.traps[Overflow] = True
        with pytest.raises(Overflow):
            cache.expire("key", Decimal("9e9"))

    assert cache.copy() == original_items
    assert cache.expire_times() == original_expirations


def test_expire_failed_timer_preserves_original_expiration():
    cache = Cache(timer=lambda: 0)
    cache.set("key", "value", ttl=5)
    cache.configure(timer=Mock(side_effect=RuntimeError("timer failed")))

    with pytest.raises(RuntimeError, match="timer failed"):
        cache.expire("key", 10)

    assert cache.copy() == {"key": "value"}
    assert cache.expire_times() == {"key": 5}


def test_expire_does_not_change_replacement_inserted_by_deletion_callback():
    now = [0]
    cache = Cache(timer=lambda: now[0])
    cache.set("key", "old", ttl=1)

    def replace(key, value, cause):
        assert (key, value, cause) == ("key", "old", RemovalCause.EXPIRED)
        cache.set(key, "new", ttl=3)

    cache.on_delete = replace
    now[0] = 1
    assert cache.expire("key", 100) is False
    assert cache.copy() == {"key": "new"}
    assert cache.expire_times() == {"key": 4}


def test_expire_propagates_deletion_callback_errors():
    now = [0]
    cache = Cache(timer=lambda: now[0])
    cache.set("key", "value", ttl=1)
    cache.on_delete = Mock(side_effect=KeyError("callback failed"))
    now[0] = 1

    with pytest.raises(KeyError, match="callback failed"):
        cache.expire("key", 10)

    assert cache.copy() == {}
    assert cache.expire_times() == {}
