
import pytest

from cacheout import Cache


parametrize = pytest.mark.parametrize


@pytest.fixture
def timer():
    def _timer():
        return _timer.time
    _timer.time = 0

    return _timer


@pytest.fixture
def cache(timer):
    return Cache(timer=timer)


@parametrize('arg,exc', [
    ({'maxsize': -1}, ValueError),
    ({'maxsize': '1'}, TypeError),
    ({'ttl': -1}, ValueError),
    ({'ttl': '1'}, TypeError),
    ({'timer': True}, TypeError),
])
def test_cache_init_validation(arg, exc):
    """Test that exceptions are raised on bad argument values/types."""
    with pytest.raises(exc):
        Cache(**arg)


def test_cache_set(cache):
    """Test that cache.set() sets cache key/value."""
    key, value = ('key', 'value')
    cache.set(key, value)
    assert cache.get(key) == value


def test_cache_set_ttl_default(cache, timer):
    """Test that cache.set() uses a default TTL if initialized with one."""
    default_ttl = 2
    cache.configure(ttl=default_ttl)

    cache.set('key', 'value')
    assert cache.has('key')

    timer.time = default_ttl - 1
    assert cache.has('key')

    timer.time = default_ttl
    assert not cache.has('key')


def test_cache_set_ttl_override(cache, timer):
    """Test that cache.set() can override the default TTL."""
    default_ttl = 1
    cache.configure(ttl=default_ttl)

    cache.set('key1', 'value1')
    cache.set('key2', 'value2', ttl=default_ttl + 1)

    timer.time = default_ttl
    assert not cache.has('key1')
    assert cache.has('key2')

    timer.time = default_ttl + 1
    assert not cache.has('key2')


def test_cache_set_many(cache):
    """Test that cache.set_many() sets multiple cache key/values."""
    items = {'a': 1, 'b': 2, 'c': 3}
    cache.set_many(items)

    for key, value in items.items():
        assert cache.get(key) == value


def test_cache_add(cache):
    """Test that cache.add() sets a cache key but only if it doesn't exist."""
    key, value = ('key', 'value')
    ttl = 2

    cache.add(key, value, ttl)
    assert cache.get(key) == value

    assert cache.expire_times()[key] == ttl

    cache.add(key, value, ttl + 1)
    assert cache.expire_times()[key] == ttl

    cache.set(key, value, ttl + 1)
    assert cache.expire_times()[key] == ttl + 1


def test_cache_add_many(cache):
    """Test that cache.add_many() adds multiple cache key/values."""
    items = {'a': 1, 'b': 2, 'c': 3}
    cache.add_many(items)

    for key, value in items.items():
        assert cache.get(key) == value


def test_cache_get(cache):
    """Test that cache.get() returns a cache key value or a default value if
    missing.
    """
    key, value = ('key', 'value')

    assert cache.get(key) is None
    assert cache.get(key, default=1) == 1

    cache.set(key, value)
    assert cache.get(key) == value


def test_cache_get_many(cache):
    """Test that cache.get_many() returns multiple cache key/values."""
    items = {'a': 1, 'b': 2, 'c': 3}
    cache.set_many(items)

    assert cache.get_many(items.keys()) == items


def test_cache_delete(cache):
    """Test that cache.delete() removes a cache key."""
    key, value = ('key', 'value')
    cache.set(key, value)
    assert cache.has(key)

    cache.delete(key)
    assert not cache.has(key)

    cache.delete(key)
    assert not cache.has(key)


def test_cache_delete_many(cache):
    """Test that cache.delete_many() deletes multiple cache key/values."""
    items = {'a': 1, 'b': 2, 'c': 3}
    cache.set_many(items)

    assert len(cache) == len(items)

    cache.delete_many(items.keys())

    assert len(cache) == 0


def test_cache_delete_expired(cache, timer):
    """Test that cache.delete_expired() removes all expired keys."""
    ttl = 1
    ttl_keys = list(range(5))
    non_ttl_keys = list(range(5, 10))
    all_keys = ttl_keys + non_ttl_keys

    for key in ttl_keys:
        cache.set(key, key, ttl=ttl)

    for key in non_ttl_keys:
        cache.set(key, key)

    assert len(cache) == len(all_keys)

    cache.delete_expired()

    assert len(cache) == len(all_keys)

    timer.time = ttl

    cache.delete_expired()

    assert len(cache) == len(non_ttl_keys)

    for key in ttl_keys:
        assert not cache.has(key)

    for key in non_ttl_keys:
        assert cache.has(key)


def test_cache_evict(cache):
    """Test that cache.evict() will remove cache keys to make room."""
    maxsize = 5
    cache.configure(maxsize=maxsize)

    for key in range(maxsize):
        cache.set(key, key)

    assert len(cache) == maxsize
    assert cache.has(0)

    for key in range(maxsize):
        next_key = -(key + 1)
        cache.set(next_key, next_key)

        assert len(cache) == maxsize
        assert not cache.has(key)


def test_cache_size(cache):
    """Test that cache.size() returns the number of cache keys."""
    assert cache.size() == len(cache) == 0

    for n in range(1, 50):
        cache.set(n, n)
        assert cache.size() == len(cache) == n


def test_cache_full(cache):
    """Test that cache.full() returns whether the cache is full or not."""
    for n in range(cache.maxsize):
        assert not cache.full()
        cache.set(n, n)

    assert cache.full()


def test_cache_full_unbounded(cache):
    """Test that cache.full() always returns False for an unbounded cache."""
    cache.configure(maxsize=0)
    for n in range(1000):
        cache.set(n, n)
        assert not cache.full()


def test_cache_has(cache):
    """Test that cache.has() returns whether a key exists or not."""
    key, value = ('key', 'value')

    assert not cache.has(key)
    assert key not in cache

    cache.set(key, value)

    assert cache.has(key)
    assert key in cache


def test_cache_has_on_expired(cache, timer):
    """Test that cache.has() takes into account expired keys."""
    key, value = ('key', 'value')

    cache.set(key, value, ttl=1)

    assert cache.has(key)
    assert key in cache

    timer.time = 1

    assert not cache.has(key)
    assert key not in cache


def test_cache_copy(cache):
    """Test that cache.copy() returns a copy of the cache."""
    items = {'a': 1, 'b': 2, 'c': 3}
    cache.set_many(items)

    copied = cache.copy()
    assert copied == items
    assert copied is not cache._cache


def test_cache_clear(cache):
    """Test that cache.clear() deletes all cache keys."""
    items = {'a': 1, 'b': 2, 'c': 3}
    cache.set_many(items)
    assert len(cache) == len(items)

    cache.clear()
    assert len(cache) == 0


def test_cache_keys(cache):
    """Test that cache.keys() returns all cache keys."""
    items = {'a': 1, 'b': 2, 'c': 3}
    cache.set_many(items)

    assert sorted(cache.keys()) == sorted(items.keys())


def test_cache_values(cache):
    """Test that cache.values() returns all cache values."""
    items = {'a': 1, 'b': 2, 'c': 3}
    cache.set_many(items)

    assert sorted(cache.values()) == sorted(items.values())


def test_cache_items(cache):
    """Test that cache.items() returns all cache key/values."""
    items = {'a': 1, 'b': 2, 'c': 3}
    cache.set_many(items)

    assert set(cache.items()) == set(items.items())


def test_cache_popitem(cache):
    """Test that cache.popitem() removes the oldest entries first."""
    keys = list(range(cache.maxsize))

    for key in keys:
        cache.set(key, str(key))

    for i, key in enumerate(keys):
        k, v = cache.popitem()
        assert k == key
        assert v == str(key)
        assert len(cache) == (cache.maxsize - (i + 1))

    with pytest.raises(KeyError):
        cache.popitem()


def test_cache_iter(cache):
    """Test that iterating over cache yields each cache key."""
    items = {'a': 1, 'b': 2, 'c': 3}
    cache.set_many(items)

    keys = []
    for key in cache:
        assert cache.get(key) == items[key]
        keys.append(key)

    assert set(keys) == set(items)


def test_cache_repr(cache):
    """Test that repr(cache) returns a representation of the cache object."""
    assert repr(cache) == 'Cache([])'

    cache.set('a', 1)
    cache.set('b', 2)
    cache.set('c', 3)

    assert repr(cache) == "Cache([('a', 1), ('b', 2), ('c', 3)])"
