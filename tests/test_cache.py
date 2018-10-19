
import asyncio
import re

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
    assert key not in cache

    cache.set(key, value)
    assert cache.get(key) == value


def test_cache_default():
    """Test that Cache can set the default for Cache.get()."""
    cache = Cache(default=True)

    assert cache.get(1) is True
    assert 1 not in cache
    assert cache.get(2, default=False) is False
    assert 2 not in cache


def test_cache_default_callable():
    """Test that Cache can set a default function for Cache.get()."""
    def default(key):
        return False

    def default_override(key):
        return key

    cache = Cache(default=default)

    assert cache.get('key1') is False
    assert cache.get('key1', default=default_override) is False
    assert cache.get('key2', default=default_override) == 'key2'
    assert cache.get('key3', default=3) == 3


def test_cache_get_default_callable(cache):
    """Test that cache.get() uses a default function when value is not found to
    set cache keys.
    """
    def default(key):
        return key

    key = 'key'

    assert cache.get(key) is None
    assert cache.get(key, default=default) == key
    assert key in cache


@parametrize('items,iteratee,expected', [
    ({'a_1': 1, 'a_2': 2, 'bcd': 3, 'bed': 4, '12345': 5},
     ['a_1', '12345'],
     {'a_1': 1, '12345': 5}),
    ({'a_1': 1, 'a_2': 2, 'bcd': 3, 'bed': 4, '12345': 5},
     'a_*',
     {'a_1': 1, 'a_2': 2}),
    ({'a_1': 1, 'a_2': 2, 'bcd': 3, 'bed': 4, '12345': 5},
     re.compile(r'\d'),
     {'12345': 5}),
    ({'a_1': 1, 'a_2': 2, 'bcd': 3, 'bed': 4, '12345': 5},
     lambda key: key.startswith('b') and key.endswith('d'),
     {'bcd': 3, 'bed': 4}),
])
def test_cache_get_many(cache, items, iteratee, expected):
    """Test that cache.get_many() returns multiple cache key/values filtered
    by an iteratee.
    """
    cache.set_many(items)
    assert cache.get_many(iteratee) == expected


def test_cache_delete(cache):
    """Test that cache.delete() removes a cache key."""
    key, value = ('key', 'value')
    cache.set(key, value)
    assert cache.has(key)

    cache.delete(key)
    assert not cache.has(key)

    cache.delete(key)
    assert not cache.has(key)


@parametrize('items,iteratee,expected', [
    ({'a_1': 1, 'a_2': 2, 'bcd': 3, 'bed': 4, '12345': 5},
     ['a_1', '12345'],
     {'a_2': 2, 'bcd': 3, 'bed': 4}),
    ({'a_1': 1, 'a_2': 2, 'bcd': 3, 'bed': 4, '12345': 5},
     ['a_1', '12345'],
     {'a_2': 2, 'bcd': 3, 'bed': 4}),
    ({'a_1': 1, 'a_2': 2, 'bcd': 3, 'bed': 4, '12345': 5},
     'a_*',
     {'bcd': 3, 'bed': 4, '12345': 5}),
    ({'a_1': 1, 'a_2': 2, 'bcd': 3, 'bed': 4, '12345': 5},
     re.compile(r'\d'),
     {'a_1': 1, 'a_2': 2, 'bcd': 3, 'bed': 4}),
    ({'a_1': 1, 'a_2': 2, 'bcd': 3, 'bed': 4, '12345': 5},
     lambda key: key.startswith('b') and key.endswith('d'),
     {'a_1': 1, 'a_2': 2, '12345': 5}),
])
def test_cache_delete_many(cache, items, iteratee, expected):
    """Test that cache.delete_many() deletes multiple cache key/values filtered
    by an iteratee.
    """
    cache.set_many(items)

    cache.delete_many(iteratee)

    assert dict(cache.items()) == expected


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


def test_cache_memoize(cache):
    """Test that cache.memoize() caches the return value of a function using a
    key based on function arguments used.
    """
    marker = 1

    @cache.memoize()
    def func(a, b, c, d):
        return ((a, b, c, d), marker)

    args, markx = func(1, 2, 3, 4)
    assert args == (1, 2, 3, 4)
    assert markx == marker

    marker += 1
    args, marky = func(1, 2, 3, 4)
    assert args == (1, 2, 3, 4)
    assert marky != marker
    assert marky == markx

    args, markz = func(5, 6, 7, 8)
    assert args == (5, 6, 7, 8)
    assert markz == marker


def test_cache_memoize_typed(cache):
    """Test that cache.memoize() can factor in argument types as part of the
    cache key.
    """
    @cache.memoize()
    def untyped(a):
        return a

    @cache.memoize(typed=True)
    def typed(a):
        return a

    assert untyped(1) is untyped(1.0)
    assert typed(1) is not typed(1.0)

    assert len(cache) == 3

    untyped_keys = [key for key in cache.keys()
                    if key.startswith('{}.{}'.format(untyped.__module__,
                                                     untyped.__name__))]

    typed_keys = [key for key in cache.keys()
                  if key.startswith('{}.{}'.format(typed.__module__,
                                                   typed.__name__))]

    assert len(untyped_keys) == 1
    assert len(typed_keys) == 2


def test_cache_memoize_arg_normalization(cache):
    """Test taht cache.memoize() normalizes argument ordering for positional
    and keyword arguments.
    """
    @cache.memoize(typed=True)
    def func(a, b, c, d, **kargs):
        return (a, b, c, d)

    for args, kargs in (((1, 2, 3, 4), {'e': 5}),
                        ((1, 2, 3), {'d': 4, 'e': 5}),
                        ((1, 2), {'c': 3, 'd': 4, 'e': 5}),
                        ((1,), {'b': 2, 'c': 3, 'd': 4, 'e': 5}),
                        ((), {'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5}),
                        ((), {'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5})):
        func(*args, **kargs)
        assert len(cache) == 1


def test_cache_memoize_ttl(cache, timer):
    """Test that cache.memoize() can set a TTL."""
    ttl1 = 5
    ttl2 = ttl1 + 1

    @cache.memoize(ttl=ttl1)
    def func1(a):
        return a

    @cache.memoize(ttl=ttl2)
    def func2(a):
        return a

    func1(1)
    func2(1)

    assert len(cache) == 2
    key1, key2 = tuple(cache.keys())

    timer.time = ttl1 - 1
    assert cache.has(key1)
    assert cache.has(key2)

    timer.time = ttl1
    assert not cache.has(key1)
    assert cache.has(key2)

    timer.time = ttl2
    assert not cache.has(key2)


def test_cache_memoize_func_attrs(cache):
    """Test that cache.memoize() adds attributes to decorated function."""
    marker = 1
    value = {}

    def original(a):
        return (a, marker)

    memoized = cache.memoize()(original)

    assert memoized.cache is cache
    assert memoized.uncached is original

    _, markx = memoized(value)
    assert markx == marker

    marker += 1
    _, marky = memoized(value)

    assert marky != marker
    assert marky == markx

    _, markz = memoized.uncached(value)
    assert markz == marker


def test_cache_memoize_coroutine(cache):
    """Test that cache.memoize() can decorate coroutines."""
    marker = 1

    @cache.memoize()
    @asyncio.coroutine
    def func(a):
        return (a, marker)

    assert asyncio.iscoroutinefunction(func)

    assert len(cache) == 0

    result = asyncio.get_event_loop().run_until_complete(func('a'))

    assert result == ('a', 1)
    assert len(cache) == 1
    assert list(cache.values())[0] == ('a', 1)

    marker += 1
    result = asyncio.get_event_loop().run_until_complete(func('a'))

    assert result == ('a', 1)
    assert len(cache) == 1

    result = asyncio.get_event_loop().run_until_complete(func('b'))

    assert result == ('b', 2)
    assert len(cache) == 2


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
