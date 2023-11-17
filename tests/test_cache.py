import asyncio
import re
import sys
import typing as t

import pytest

from cacheout import UNSET, Cache, RemovalCause


parametrize = pytest.mark.parametrize


class Timer:
    def __init__(self) -> None:
        self.time: t.Union[int, float] = 0

    def __call__(self) -> t.Union[int, float]:
        return self.time


@pytest.fixture
def timer() -> Timer:
    return Timer()


@pytest.fixture
def cache(timer) -> Cache:
    return Cache(timer=timer)


@parametrize(
    "args, exc",
    [
        ({"maxsize": -1}, ValueError),
        ({"maxsize": "1"}, TypeError),
        ({"ttl": -1}, ValueError),
        ({"ttl": "1"}, TypeError),
        ({"timer": True}, TypeError),
        ({"enable_stats": None}, TypeError),
    ],
)
def test_cache_init_validation(args: dict, exc: t.Type[Exception]):
    """Test that exceptions are raised on bad argument values/types."""
    with pytest.raises(exc):
        Cache(**args)


def test_cache_set(cache: Cache):
    """Test that cache.set() sets cache key/value."""
    key, value = ("key", "value")
    cache.set(key, value)
    assert cache.get(key) == value


def test_cache_set_ttl_default(cache: Cache, timer: Timer):
    """Test that cache.set() uses a default TTL if initialized with one."""
    default_ttl = 2
    cache.configure(ttl=default_ttl)

    cache.set("key", "value")
    assert cache.has("key")

    timer.time = default_ttl - 1
    assert cache.has("key")

    timer.time = default_ttl
    assert not cache.has("key")


def test_cache_set_ttl_override(cache: Cache, timer: Timer):
    """Test that cache.set() can override the default TTL."""
    default_ttl = 1
    cache.configure(ttl=default_ttl)

    cache.set("key1", "value1")
    cache.set("key2", "value2", ttl=default_ttl + 1)

    timer.time = default_ttl
    assert not cache.has("key1")
    assert cache.has("key2")

    timer.time = default_ttl + 1
    assert not cache.has("key2")


def test_cache_set_many(cache: Cache):
    """Test that cache.set_many() sets multiple cache key/values."""
    items = {"a": 1, "b": 2, "c": 3}
    cache.set_many(items)

    for key, value in items.items():
        assert cache.get(key) == value


def test_cache_add(cache: Cache):
    """Test that cache.add() sets a cache key but only if it doesn't exist."""
    key, value = ("key", "value")
    ttl = 2

    cache.add(key, value, ttl)
    assert cache.get(key) == value

    assert cache.expire_times()[key] == ttl

    cache.add(key, value, ttl + 1)
    assert cache.expire_times()[key] == ttl

    cache.set(key, value, ttl + 1)
    assert cache.expire_times()[key] == ttl + 1


def test_cache_add_many(cache: Cache):
    """Test that cache.add_many() adds multiple cache key/values."""
    items = {"a": 1, "b": 2, "c": 3}
    cache.add_many(items)

    for key, value in items.items():
        assert cache.get(key) == value


def test_cache_get(cache: Cache):
    """Test that cache.get() returns a cache key value or a default value if missing."""
    key, value = ("key", "value")

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

    assert cache.get("key1") is False
    assert cache.get("key1", default=default_override) is False
    assert cache.get("key2", default=default_override) == "key2"
    assert cache.get("key3", default=3) == 3


def test_cache_get_default_callable(cache: Cache):
    """Test that cache.get() uses a default function when value is not found to set cache keys."""

    def default(key):
        return key

    key = "key"

    assert cache.get(key) is None
    assert cache.get(key, default=default) == key
    assert key in cache


@parametrize(
    "items, iteratee, expected",
    [
        (
            {"a_1": 1, "a_2": 2, "bcd": 3, "bed": 4, "12345": 5},
            ["a_1", "12345"],
            {"a_1": 1, "12345": 5},
        ),
        (
            {"a_1": 1, "a_2": 2, "bcd": 3, "bed": 4, "12345": 5},
            "a_*",
            {"a_1": 1, "a_2": 2},
        ),
        (
            {"a_1": 1, "a_2": 2, "bcd": 3, "bed": 4, "12345": 5},
            re.compile(r"\d"),
            {"12345": 5},
        ),
        (
            {"a_1": 1, "a_2": 2, "bcd": 3, "bed": 4, "12345": 5},
            lambda key: key.startswith("b") and key.endswith("d"),
            {"bcd": 3, "bed": 4},
        ),
    ],
)
def test_cache_get_many(
    cache: Cache, items: dict, iteratee: t.Union[list, str, t.Pattern, t.Callable], expected: dict
):
    """Test that cache.get_many() returns multiple cache key/values filtered by an iteratee."""
    cache.set_many(items)
    assert cache.get_many(iteratee) == expected


@parametrize(
    "items, iteratee, expected",
    [
        (
            {"a_1": 1, "a_2": 2, "bcd": 3, "bed": 4, "12345": 5},
            ["a_1", "12345"],
            {"a_1": 1, "12345": 5},
        ),
        (
            {"a_1": 1, "a_2": 2, "bcd": 3, "bed": 4, "12345": 5},
            "a_*",
            {"a_1": 1, "a_2": 2},
        ),
        (
            {"a_1": 1, "a_2": 2, "bcd": 3, "bed": 4, "12345": 5},
            re.compile(r"\d"),
            {"12345": 5},
        ),
        (
            {"a_1": 1, "a_2": 2, "bcd": 3, "bed": 4, "12345": 5},
            lambda key: key.startswith("b") and key.endswith("d"),
            {"bcd": 3, "bed": 4},
        ),
    ],
)
def test_cache_get_many__ttl_expires_during_call(
    items: dict, iteratee: t.Union[list, str, t.Pattern, t.Callable], expected: dict
):
    """Test that cache.get_many() returns without error when cache keys expire during call."""
    cache = Cache(ttl=1, timer=lambda: 0)

    cache.set_many(items)
    assert cache.get_many(iteratee) == expected

    cache.timer = lambda: 100
    assert cache.get_many(iteratee) == {}


def test_cache_delete(cache: Cache):
    """Test that cache.delete() removes a cache key."""
    key, value = ("key", "value")
    cache.set(key, value)
    assert cache.has(key)

    cache.delete(key)
    assert not cache.has(key)

    cache.delete(key)
    assert not cache.has(key)


@parametrize(
    "items,iteratee,expected",
    [
        (
            {"a_1": 1, "a_2": 2, "bcd": 3, "bed": 4, "12345": 5},
            ["a_1", "12345"],
            {"a_2": 2, "bcd": 3, "bed": 4},
        ),
        (
            {"a_1": 1, "a_2": 2, "bcd": 3, "bed": 4, "12345": 5},
            ["a_1", "12345"],
            {"a_2": 2, "bcd": 3, "bed": 4},
        ),
        (
            {"a_1": 1, "a_2": 2, "bcd": 3, "bed": 4, "12345": 5},
            "a_*",
            {"bcd": 3, "bed": 4, "12345": 5},
        ),
        (
            {"a_1": 1, "a_2": 2, "bcd": 3, "bed": 4, "12345": 5},
            re.compile(r"\d"),
            {"a_1": 1, "a_2": 2, "bcd": 3, "bed": 4},
        ),
        (
            {"a_1": 1, "a_2": 2, "bcd": 3, "bed": 4, "12345": 5},
            lambda key: key.startswith("b") and key.endswith("d"),
            {"a_1": 1, "a_2": 2, "12345": 5},
        ),
    ],
)
def test_cache_delete_many(
    cache: Cache, items: dict, iteratee: t.Union[list, str, t.Pattern, t.Callable], expected: dict
):
    """Test that cache.delete_many() deletes multiple cache key/values filtered by an iteratee."""
    cache.set_many(items)

    cache.delete_many(iteratee)

    assert dict(cache.items()) == expected


def test_cache_delete_expired(cache: Cache, timer: Timer):
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


def test_cache_get_ttl(cache: Cache, timer: Timer):
    """Test that cache.get_ttl() will return the remaining time to live of a key that has a TTL."""
    cache.set("a", 1, ttl=1)
    cache.set("b", 2, ttl=2)
    cache.set("c", 3)

    assert cache.get_ttl("a") == 1

    timer.time = 1

    assert cache.get_ttl("a") is None
    assert cache.get_ttl("b") == 1
    assert cache.get_ttl("c") is None


def test_cache_evict(cache: Cache):
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


def test_cache_memoize(cache: Cache):
    """Test that cache.memoize() caches the return value of a function using a key based on function
    arguments used."""
    marker = 1

    @cache.memoize()
    def func(a, b, c, d):
        return (a, b, c, d), marker

    args, mark_x = func(1, 2, 3, 4)
    assert args == (1, 2, 3, 4)
    assert mark_x == marker

    marker += 1
    args, mark_y = func(1, 2, 3, 4)
    assert args == (1, 2, 3, 4)
    assert mark_y != marker
    assert mark_y == mark_x

    args, mark_z = func(5, 6, 7, 8)
    assert args == (5, 6, 7, 8)
    assert mark_z == marker


def test_cache_memoize_typed(cache: Cache):
    """Test that cache.memoize() can factor in argument types as part of the cache key."""

    @cache.memoize()
    def untyped(a):
        return a

    @cache.memoize(typed=True)
    def typed(a):
        return a

    assert untyped(1) is untyped(1.0)
    assert typed(1) is not typed(1.0)

    assert len(cache) == 3

    untyped_keys = [
        key for key in cache.keys() if key.startswith(f"{untyped.__module__}.{untyped.__name__}")
    ]

    typed_keys = [
        key for key in cache.keys() if key.startswith(f"{typed.__module__}.{typed.__name__}")
    ]

    assert len(untyped_keys) == 1
    assert len(typed_keys) == 2


def test_cache_memoize_arg_normalization(cache: Cache):
    """Test that cache.memoize() normalizes argument ordering for positional and keyword
    arguments."""

    @cache.memoize(typed=True)
    def func(a, b, c, d, **kwargs):
        return a, b, c, d

    for args, kwargs in (
        ((1, 2, 3, 4), {"e": 5}),
        ((1, 2, 3), {"d": 4, "e": 5}),
        ((1, 2), {"c": 3, "d": 4, "e": 5}),
        ((1,), {"b": 2, "c": 3, "d": 4, "e": 5}),
        ((), {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}),
        ((), {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}),
    ):
        cached = func(*args, **kwargs)
        assert cache.get(func.cache_key(*args, **kwargs)) is cached
        assert len(cache) == 1


def test_cache_memoize_ttl(cache: Cache, timer: Timer):
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


def test_cache_memoize_func_attrs(cache: Cache):
    """Test that cache.memoize() adds attributes to decorated function."""
    marker = 1
    value: dict = {}

    def original(a):
        return a, marker

    memoized = cache.memoize()(original)

    assert memoized.cache is cache
    assert memoized.uncached is original
    assert hasattr(memoized, "cache_key") and callable(memoized.cache_key)

    _, mark_x = memoized(value)
    assert mark_x == marker

    marker += 1
    _, mark_y = memoized(value)

    assert mark_y != marker
    assert mark_y == mark_x

    _, mark_z = memoized.uncached(value)
    assert mark_z == marker


async def test_cache_memoize_async(cache: Cache):
    """Test that cache.memoize() can decorate async functions."""
    marker = 1

    @cache.memoize()
    async def func(a):
        return a, marker

    assert asyncio.iscoroutinefunction(func)

    assert len(cache) == 0

    result = await func("a")

    assert result == ("a", 1)
    assert len(cache) == 1
    assert list(cache.values())[0] == ("a", 1)

    marker += 1
    result = await func("a")

    assert result == ("a", 1)
    assert len(cache) == 1

    result = await func("b")

    assert result == ("b", 2)
    assert len(cache) == 2


@pytest.mark.skipif(sys.version_info[:2] <= (3, 8), reason="test not compatible with python <= 3.8")
async def test_cache_memoize_async_runtime_error_regression(cache: Cache):
    """
    Test that cache.memoize() doesn't raise RuntimeError.

    Note:
        There's something different about asyncio.create_subprocess_exec() that caused
        a previous implementation of cache.memoize() to fail with "RuntimeError: await
        wasn't used with future".
    """

    @cache.memoize()
    async def func():
        # NOTE: There's something different about create_subprocess_exec() that caused
        # a previous implementation of cache.memoize() to fail with "RuntimeError: await wasn't used
        # with future". So we're specifically testing against that.
        proc = await asyncio.create_subprocess_exec("python", "--version")
        proc.terminate()

    await func()


def test_cache_size(cache: Cache):
    """Test that cache.size() returns the number of cache keys."""
    assert cache.size() == len(cache) == 0

    for n in range(1, 50):
        cache.set(n, n)
        assert cache.size() == len(cache) == n


def test_cache_full(cache: Cache):
    """Test that cache.full() returns whether the cache is full or not."""
    for n in range(cache.maxsize):
        assert not cache.full()
        cache.set(n, n)

    assert cache.full()


def test_cache_full_unbounded(cache: Cache):
    """Test that cache.full() always returns False for an unbounded cache."""
    cache.configure(maxsize=0)
    for n in range(1000):
        cache.set(n, n)
        assert not cache.full()


def test_cache_full_maxsize_none():
    """Test that cache.full() works when maxsize is None."""
    cache = Cache(maxsize=None)
    for n in range(1000):
        cache.set(n, n)
        assert not cache.full()


def test_cache_full_maxsize_negative():
    """Test that cache.full() works when maxsize is negative."""
    cache = Cache()
    cache.maxsize = -1
    for n in range(1000):
        cache.set(n, n)
        assert not cache.full()


def test_cache_has(cache: Cache):
    """Test that cache.has() returns whether a key exists or not."""
    key, value = ("key", "value")

    assert not cache.has(key)
    assert key not in cache

    cache.set(key, value)

    assert cache.has(key)
    assert key in cache


def test_cache_has_on_expired(cache, timer: Timer):
    """Test that cache.has() takes into account expired keys."""
    key, value = ("key", "value")

    cache.set(key, value, ttl=1)

    assert cache.has(key)

    timer.time = 1

    assert not cache.has(key)


def test_cache_contains_on_expired(cache, timer: Timer):
    """Test that "key in cache" takes into account expired keys."""
    key, value = ("key", "value")

    cache.set(key, value, ttl=1)

    assert key in cache

    timer.time = 1

    assert key not in cache


def test_cache_copy(cache: Cache):
    """Test that cache.copy() returns a copy of the cache."""
    items = {"a": 1, "b": 2, "c": 3}
    cache.set_many(items)

    copied = cache.copy()
    assert copied == items
    assert copied is not cache._cache


def test_cache_clear(cache: Cache):
    """Test that cache.clear() deletes all cache keys."""
    items = {"a": 1, "b": 2, "c": 3}
    cache.set_many(items)
    assert len(cache) == len(items)

    cache.clear()
    assert len(cache) == 0


def test_cache_keys(cache: Cache):
    """Test that cache.keys() returns all cache keys."""
    items = {"a": 1, "b": 2, "c": 3}
    cache.set_many(items)

    assert sorted(cache.keys()) == sorted(items.keys())


def test_cache_values(cache: Cache):
    """Test that cache.values() returns all cache values."""
    items = {"a": 1, "b": 2, "c": 3}
    cache.set_many(items)

    assert sorted(cache.values()) == sorted(items.values())


def test_cache_items(cache: Cache):
    """Test that cache.items() returns all cache key/values."""
    items = {"a": 1, "b": 2, "c": 3}
    cache.set_many(items)

    assert set(cache.items()) == set(items.items())


def test_cache_popitem(cache: Cache):
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


def test_cache_iter(cache: Cache):
    """Test that iterating over cache yields each cache key."""
    items: dict = {"a": 1, "b": 2, "c": 3}
    cache.set_many(items)

    keys = []
    for key in cache:
        assert cache.get(key) == items[key]
        keys.append(key)

    assert set(keys) == set(items)


def test_cache_repr(cache: Cache):
    """Test that repr(cache) returns a representation of the cache object."""
    cache_id = id(cache)
    assert repr(cache) == f"Cache(id={cache_id}, total_entries=0)"

    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)

    assert repr(cache) == f"Cache(id={cache_id}, total_entries=3)"


def test_cache_on_delete(cache: Cache, timer: Timer):
    """Test that on_delete(cache) callback."""
    log = ""

    def on_delete(key, value, cause):
        nonlocal log
        log = f"{key}={value}, RemovalCause={cause.value}"

    cache.on_delete = on_delete
    cache.set("DELETE", 1)
    cache.delete("DELETE")
    assert log == f"DELETE=1, RemovalCause={RemovalCause.DELETE.value}"

    cache.clear()
    cache.set("POPITEM", 1)
    cache.popitem()
    assert log == f"POPITEM=1, RemovalCause={RemovalCause.POPITEM.value}"

    cache.set("EXPIRED", 1, ttl=1)
    timer.time = 1
    cache.delete_expired()
    assert log == f"EXPIRED=1, RemovalCause={RemovalCause.EXPIRED.value}"

    cache.clear()
    cache.maxsize = 1
    cache.set("FULL", 1)
    cache.set("OVERFLOW", 2)
    assert log == f"FULL=1, RemovalCause={RemovalCause.FULL.value}"


def test_cache_on_get(cache: Cache):
    """Test that on_get(cache) callback."""
    log = ""

    def on_get(key, value, existed):
        nonlocal log
        log = f"{key}={value}, existed={existed}"

    cache.on_get = on_get
    cache.set("hit", 1)

    cache.get("hit")
    assert log == "hit=1, existed=True"

    cache.get("miss")
    assert log == "miss=None, existed=False"


def test_cache_on_set(cache: Cache):
    """Test that on_set(cache) callback."""
    log = {}

    def on_set(key, new_value, old_value):
        nonlocal log
        log = {"key": key, "new_value": new_value, "old_value": old_value}

    cache.on_set = on_set

    cache.set("a", 1)
    assert log == {"key": "a", "new_value": 1, "old_value": UNSET}

    cache.set("a", 2)
    assert log == {"key": "a", "new_value": 2, "old_value": 1}


def test_cache_stats__disabled_by_default(cache: Cache):
    """Test that cache stats are disabled by default."""
    assert cache.stats.is_enabled() is False


def test_cache_stats__enable_on_init():
    """Test that cache stats can be enabled on init."""
    cache = Cache(enable_stats=True)
    assert cache.stats.is_enabled() is True


def test_cache_stats_configure(cache: Cache):
    """Test that cache stats can enabled/disabled on configure."""
    assert cache.stats.is_enabled() is False
    cache.configure(enable_stats=True)

    assert cache.stats.is_enabled() is True
    cache.configure(enable_stats=False)
    assert cache.stats.is_enabled() is False
