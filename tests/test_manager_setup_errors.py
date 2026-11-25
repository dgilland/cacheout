import pytest

from cacheout import Cache, CacheManager


@pytest.mark.parametrize("settings", [[], {"new": {}, "invalid": {"maxsize": -1}}])
def test_failed_setup_preserves_existing_caches(settings):
    manager = CacheManager({"original": {"ttl": 10}})
    original = manager["original"]
    original.set("saved", "value")
    expiration = original.expire_times()

    with pytest.raises((TypeError, ValueError)):
        manager.setup(settings)

    assert manager.cache_names() == ["original"]
    assert manager["original"] is original
    assert original.copy() == {"saved": "value"}
    assert original.expire_times() == expiration


def test_failed_factory_preserves_registry_and_propagates_error():
    manager = CacheManager({"original": {}})
    original = manager["original"]
    expected = RuntimeError("cache backend unavailable")

    def factory(**options):
        if options.get("fail"):
            raise expected
        return Cache(**options)

    manager.cache_class = factory
    with pytest.raises(RuntimeError) as caught:
        manager.setup({"new": {}, "unavailable": {"fail": True}})

    assert caught.value is expected
    assert dict(manager) == {"original": original}
