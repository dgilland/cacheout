from decimal import Decimal, Overflow, localcontext

import pytest

from cacheout import Cache, FIFOCache, LFUCache, LIFOCache, LRUCache, MRUCache, RRCache


@pytest.mark.parametrize(
    "cache_class", [Cache, FIFOCache, LFUCache, LIFOCache, LRUCache, MRUCache, RRCache]
)
@pytest.mark.parametrize("operation", ["insert", "replace", "evict"])
def test_failed_expiration_preserves_cache(cache_class, operation):
    """An overflowing deadline must not leave an immortal value or evict a live one."""
    cache = cache_class(maxsize=1, timer=lambda: Decimal("9e9"), enable_stats=True)
    if operation != "insert":
        cache.set("original", "old value", ttl=Decimal(20))
    key = "original" if operation == "replace" else "new"
    original_items = cache.copy()
    original_expirations = cache.expire_times()

    with localcontext() as context:
        context.Emax = 9
        context.traps[Overflow] = True
        with pytest.raises(Overflow):
            cache.set(key, "rejected value", ttl=Decimal("9e9"))

    assert cache.copy() == original_items
    assert cache.expire_times() == original_expirations
    assert cache.stats.info().eviction_count == 0

    # The replacement policy must still be usable after the failed write.
    if original_items:
        assert cache.popitem() == ("original", "old value")
    cache.set("recovered", "new value", ttl=Decimal(5))
    assert cache.popitem() == ("recovered", "new value")


@pytest.mark.parametrize("replace", [False, True])
def test_failed_timer_preserves_cache(replace):
    cache = Cache(timer=lambda: 0)
    if replace:
        cache.set("key", "old value", ttl=10)
    original_items = cache.copy()
    original_expirations = cache.expire_times()

    def failed_timer():
        raise RuntimeError("timer failed")

    cache.configure(timer=failed_timer)
    with pytest.raises(RuntimeError, match="timer failed"):
        cache.set("key", "rejected value", ttl=5)

    assert cache.copy() == original_items
    assert cache.expire_times() == original_expirations
