from threading import Event, RLock, Thread, current_thread

import pytest

from cacheout import Cache, CacheManager


parametrize = pytest.mark.parametrize


class MyCache(Cache):
    pass


class CoordinatedLock:
    def __init__(self, worker, waiting):
        self.lock = RLock()
        self.worker = worker
        self.waiting = waiting

    def __enter__(self):
        if current_thread() is self.worker:
            self.waiting.set()
        if not self.lock.acquire(timeout=5):
            raise TimeoutError("cache manager operation remained blocked")
        return self

    def __exit__(self, *args):
        self.lock.release()


def assert_cache_options(cache: Cache, options: dict):
    for opt, val in options.items():
        assert getattr(cache, opt) == val


def test_cache_manager_init_configure():
    """Test that CacheManager can configure bulk caches."""
    settings = {
        "a": {},
        "b": {"maxsize": 10},
        "c": {"ttl": 60},
        "d": {"maxsize": 10, "ttl": 60},
    }
    cacheman = CacheManager(settings)

    for name, options in settings.items():
        cache = cacheman[name]
        assert isinstance(cache, Cache)
        assert_cache_options(cache, options)


def test_cache_manager_configure():
    """Test that CacheManager can configure individual caches."""
    name = "a"
    options = {"maxsize": 10, "ttl": 60}
    cacheman = CacheManager()
    cacheman.configure(name, **options)

    assert_cache_options(cacheman[name], options)


def test_cache_manager_reconfigure():
    """Test that CacheManager can reconfigure a previously configured cache."""
    name = "a"
    options = {"maxsize": 10, "ttl": 60}
    cacheman = CacheManager()
    cacheman.configure(name, **options)

    # Store copy of cache to verify identity doesn't change.
    cache = cacheman[name]

    new_options = {"maxsize": options["maxsize"] * 2, "ttl": options["ttl"] / 2}

    cacheman.configure(name, **new_options)

    assert_cache_options(cacheman[name], new_options)
    assert cacheman[name] is cache


@parametrize("action", ["configure", "register", "setup"])
def test_cache_manager_serializes_creation(monkeypatch, action):  # noqa: PLR0915
    """Coordinate both operations and release/join workers even when an assertion fails."""
    creating = Event()
    release = Event()
    competing = Event()
    created = []
    errors = []

    def factory(**options):
        cache = Cache(**options)
        cache.set("saved", "value")
        created.append(cache)
        if len(created) == 1:
            creating.set()
            assert release.wait(5)
        return cache

    manager = CacheManager(cache_class=factory)
    registered = Cache(maxsize=20)

    def configure_first():
        try:
            manager.configure("shared", maxsize=10)
        except Exception as exc:
            errors.append(exc)

    def configure_second():
        try:
            if action == "configure":
                manager.configure("shared", maxsize=20)
            elif action == "register":
                manager.register("shared", registered)
            else:
                manager.setup({"shared": {"maxsize": 20}})
        except Exception as exc:
            errors.append(exc)
        finally:
            competing.set()

    first = Thread(target=configure_first, daemon=True)
    second = Thread(target=configure_second, daemon=True)
    monkeypatch.setattr(manager, "_lock", CoordinatedLock(second, competing))
    try:
        first.start()
        assert creating.wait(5)
        second.start()
        assert competing.wait(5)
    finally:
        release.set()
        first.join(6)
        if second.ident is not None:
            second.join(6)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert len(created) == (2 if action == "setup" else 1)
    assert manager["shared"].maxsize == 20
    if action != "register":
        assert manager["shared"] is created[-1]
        assert manager["shared"].get("saved") == "value"
    else:
        assert manager["shared"] is registered


def test_cache_manager_setup():
    """Test that CacheManager.setup() initializes caches."""
    settings = {str(n): {} for n in range(5)}
    cacheman = CacheManager(settings)
    caches = {name: cache for name, cache in cacheman}

    for name in settings.keys():
        assert name in cacheman

    # Empty settings will delete cache instances.
    cacheman.setup()

    for name in settings.keys():
        assert name not in cacheman

    # Setup again to create all new cache instances.
    cacheman.setup(settings)

    for name, options in settings.items():
        cache = cacheman[name]
        assert_cache_options(cache, options)
        assert cache is not caches[name]


def test_cache_manager_invalid_settings():
    """Test that CacheManager raises on invalid settings."""
    with pytest.raises(TypeError):
        CacheManager([{}])


def test_cache_manager_default_cache_class():
    """Test that CacheManager can use a custom default cache class."""
    cacheman = CacheManager(cache_class=MyCache)
    cacheman.configure("a")

    assert isinstance(cacheman["a"], MyCache)


def test_cache_manager_configure_class():
    """Test that CacheManager can configure caches with a custom cache class."""
    cacheman = CacheManager({"a": {"cache_class": MyCache}})
    assert isinstance(cacheman["a"], MyCache)

    cacheman = CacheManager()
    cacheman.configure("a", cache_class=MyCache)
    assert isinstance(cacheman["a"], MyCache)


def test_cache_manager_cache_names():
    """Test that CacheManager can return a list of cache names."""
    settings = {str(n): {} for n in range(5)}
    cacheman = CacheManager(settings)

    names = cacheman.cache_names()

    assert isinstance(names, list)
    assert set(names) == set(settings)


def test_cache_manager_caches():
    """Test that CacheManager can return a list of caches."""
    settings = {str(n): {} for n in range(5)}
    cacheman = CacheManager(settings)

    caches = cacheman.caches()

    assert isinstance(caches, list)
    assert len(caches) == len(settings)

    for _, cache in cacheman:
        assert cache in caches


def test_cache_manager_clear_all():
    """That that CacheManager can clear all caches."""
    settings = {str(n): {} for n in range(5)}
    cacheman = CacheManager(settings)

    for _, cache in cacheman:
        cache.set(1, 1)
        assert len(cache) == 1

    cacheman.clear_all()

    for _, cache in cacheman:
        assert len(cache) == 0


def test_cache_manager_contains():
    """Test that CacheManager contains returns whether named cache exists."""
    settings = {str(n): {} for n in range(5)}
    cacheman = CacheManager(settings)

    for name in settings.keys():
        assert name in cacheman


def test_cache_manager_to_dict():
    """Test that CacheManager can be converted to a dict."""
    settings = {str(n): {} for n in range(5)}
    cacheman = CacheManager(settings)

    assert dict(cacheman) == {name: cacheman[name] for name in settings.keys()}


def test_cache_manager_repr():
    settings = {"a": {}, "b": {}, "c": {}}
    cacheman = CacheManager()

    assert repr(cacheman) == "CacheManager([])"

    cacheman.setup(settings)

    assert repr(cacheman) == "CacheManager(['a', 'b', 'c'])"


def test_cache_manager_propagates_existing_cache_configuration_key_error():
    class ProfileCache(Cache):
        def configure(self, **options):
            if "profile" in options:
                raise expected
            super().configure(**options)

    expected = KeyError("missing profile")
    constructions = []

    def factory(**options):
        constructions.append(options)
        return ProfileCache()

    manager = CacheManager(cache_class=factory)
    manager.configure("existing")
    original = manager["existing"]
    original.set("saved", "value")
    with pytest.raises(KeyError) as caught:
        manager.configure("existing", profile="missing")
    assert caught.value is expected
    assert len(constructions) == 1
    assert manager["existing"] is original
    assert manager["existing"].get("saved") == "value"


@pytest.mark.parametrize(
    "settings",
    [
        [{}],
        {"created": {}, "invalid": {"maxsize": "bad"}},
        {"created": {}, "invalid": None},
    ],
)
def test_cache_manager_failed_setup_keeps_existing_caches(settings):
    manager = CacheManager({"existing": {}})
    original = manager["existing"]
    original.set("saved", "value")

    with pytest.raises(TypeError):
        manager.setup(settings)

    assert dict(manager) == {"existing": original}
    assert manager["existing"].get("saved") == "value"


def test_cache_manager_setup_preserves_caches_when_factory_raises():
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


def test_cache_manager_setup_publishes_replacements_after_all_factories_finish():
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
