import pytest

from cacheout import Cache, CacheManager


parametrize = pytest.mark.parametrize


class MyCache(Cache):
    pass


def assert_cache_options(cache, options):
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
    """Thest that CacheManager raises on invalid settings."""
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
