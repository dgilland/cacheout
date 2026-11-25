from threading import Event, Thread

import pytest

from cacheout import Cache, CacheManager


@pytest.mark.parametrize(
    "settings",
    [
        [{}],
        {"created": {}, "invalid": {"maxsize": "bad"}},
        {"created": {}, "invalid": None},
    ],
)
def test_failed_setup_keeps_existing_caches(settings):
    manager = CacheManager({"existing": {}})
    original = manager["existing"]
    original.set("saved", "value")

    with pytest.raises(TypeError):
        manager.setup(settings)

    assert dict(manager) == {"existing": original}
    assert manager["existing"].get("saved") == "value"


def test_setup_preserves_caches_when_factory_raises():
    manager = CacheManager({"existing": {}})
    original = manager["existing"]
    original.set("saved", "value")
    error = RuntimeError("cache factory failed")

    def fail(**options):
        raise error

    with pytest.raises(RuntimeError) as caught:
        manager.setup({"created": {}, "invalid": {"cache_class": fail}})

    assert caught.value is error
    assert dict(manager) == {"existing": original}
    assert original.get("saved") == "value"


def test_setup_publishes_replacements_after_all_factories_finish():
    manager = CacheManager({"existing": {}})
    original = manager["existing"]
    creating = Event()
    release = Event()
    errors = []

    def wait_for_release(**options):
        creating.set()
        assert release.wait(5)
        return Cache(**options)

    def replace():
        try:
            manager.setup({"first": {}, "second": {"cache_class": wait_for_release}})
        except Exception as error:
            errors.append(error)

    worker = Thread(target=replace, daemon=True)
    try:
        worker.start()
        assert creating.wait(5)
        assert manager["existing"] is original
        assert "first" not in manager
        assert "second" not in manager
    finally:
        release.set()
        worker.join(6)

    assert not worker.is_alive()
    assert errors == []
    assert set(manager.cache_names()) == {"first", "second"}
