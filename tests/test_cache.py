import asyncio
from dataclasses import dataclass, field
from decimal import Decimal, Overflow, localcontext
from functools import partial
import gc
import re
import typing as t
import weakref

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


CACHE_CLASSES = [Cache, FIFOCache, LFUCache, LIFOCache, LRUCache, MRUCache, RRCache]


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

    # Memoize keys are (func, frozen_args) tuples, so match on the function.
    untyped_keys = [key for key in cache.keys() if key[0] is untyped.uncached]
    typed_keys = [key for key in cache.keys() if key[0] is typed.uncached]

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


@pytest.mark.asyncio
async def test_cache_memoize_async(cache: Cache):
    """Test that cache.memoize() can decorate async functions."""
    marker = 1

    @cache.memoize()
    async def func(a):
        return a, marker

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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
@parametrize("typed", [False, True])
@parametrize("use_partial", [False, True])
async def test_memoize_async_callable_instance(cache: Cache, typed: bool, use_partial: bool):
    @dataclass
    class AsyncCallable:
        calls: int = 0

        async def __call__(self, value, *, offset=0):
            self.calls += 1
            await asyncio.sleep(0)
            return value + offset

    instance = AsyncCallable()
    target = partial(instance, offset=10) if use_partial else instance
    memoized = cache.memoize(typed=typed)(target)
    expected = 12 if use_partial else 2

    assert await memoized(2) == expected
    assert await memoized(value=2) == expected
    assert instance.calls == 1
    assert cache.get(memoized.cache_key(2)) == expected
    assert memoized.uncached is target
    assert memoized.invalidate() == 1
    assert await memoized(2) == expected
    assert instance.calls == 2


@pytest.mark.asyncio
async def test_memoize_async_callable_failure_is_not_cached(cache: Cache):
    class AsyncCallable:
        def __init__(self):
            self.calls = 0

        async def __call__(self):
            self.calls += 1
            if self.calls == 1:
                raise ValueError("try again")
            return 42

    instance = AsyncCallable()
    memoized = cache.memoize()(instance)
    with pytest.raises(ValueError, match="try again"):
        await memoized()
    assert len(cache) == 0
    assert await memoized() == 42
    assert await memoized() == 42
    assert instance.calls == 2


def test_memoize_class_with_async_call_is_synchronous(cache: Cache):
    class AsyncCallable:
        async def __call__(self):
            return 42

    constructor = cache.memoize()(AsyncCallable)
    instance = constructor()
    assert isinstance(instance, AsyncCallable)
    assert constructor() is instance


def test_cache_size(cache: Cache):
    """Test that cache.size() returns the number of cache keys."""
    assert cache.size() == len(cache) == 0

    for n in range(1, 50):
        cache.set(n, n)
        assert cache.size() == len(cache) == n


def test_cache_full(cache: Cache):
    """Test that cache.full() returns whether the cache is full or not."""
    assert cache.maxsize is not None
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
    assert cache.maxsize is not None
    keys = list(range(cache.maxsize))

    for key in keys:
        cache.set(key, str(key))

    for i, key in enumerate(keys):
        k, v = cache.popitem()
        assert k == key
        assert v == str(key)
        assert len(cache) == (cache.maxsize - (i + 1))

    with pytest.raises(StopIteration):
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


def test_cache_expired_accepts_zero_timestamp(cache: Cache, timer: Timer):
    """An explicit zero timestamp must not be replaced with the current time."""
    cache.set("key", "value", ttl=5)
    timer.time = 10
    assert not cache.expired("key", expires_on=0)
    assert not cache.expired("key", expires_on=4)
    assert cache.expired("key", expires_on=5)
    assert cache.expired("key")
    assert cache.expired("missing", expires_on=0)


def test_cache_memoize_argument_boundaries(cache: Cache):
    """Different integer argument partitions must not share cached results."""

    @cache.memoize()
    def join_numbers(*values):
        return values

    assert join_numbers(1, 23) == (1, 23)
    assert join_numbers(12, 3) == (12, 3)
    assert join_numbers(123) == (123,)
    assert join_numbers.cache_key(1, 23) != join_numbers.cache_key(12, 3)


@parametrize("typed", [False, True])
def test_memoize_partial_function(cache: Cache, typed: bool):
    calls = []

    def add(left, right):
        calls.append((left, right))
        return left + right

    target = partial(add, 10)
    memoized = cache.memoize(typed=typed)(target)
    assert memoized(2) == 12
    assert memoized(right=2) == 12
    assert calls == [(10, 2)]
    assert memoized.uncached is target


@pytest.mark.asyncio
@parametrize("typed", [False, True])
async def test_memoize_async_partial_function(cache: Cache, typed: bool):
    calls = []

    async def add(left, right):
        calls.append((left, right))
        return left + right

    target = partial(add, 10)
    memoized = cache.memoize(typed=typed)(target)
    assert await memoized(2) == 12
    assert await memoized(right=2) == 12
    assert calls == [(10, 2)]
    assert memoized.uncached is target


@pytest.mark.parametrize("typed", [False, True])
def test_cache_memoize_omitted_positional_defaults(cache: Cache, typed: bool):
    @cache.memoize(typed=typed)
    def func(a=1, b=2, c=3):
        return a, b, c

    assert func(b=4) == (1, 4, 3)
    assert func(4) == (4, 2, 3)
    assert func(c=4) == (1, 2, 4)
    assert func(1, c=4) == (1, 2, 4)
    assert func(1, 4) == (1, 4, 3)
    assert func(b=4, c=5) == (1, 4, 5)
    assert func(4, 5) == (4, 5, 3)
    assert func.cache_key(b=4) != func.cache_key(4)
    assert func.cache_key(c=4) != func.cache_key(4)
    assert func.cache_key(1, c=4) != func.cache_key(1, 4)
    assert func.cache_key(a=1, b=4, c=5) == func.cache_key(1, 4, 5)


@pytest.mark.asyncio
@pytest.mark.parametrize("typed", [False, True])
async def test_cache_memoize_async_omitted_positional_defaults(cache: Cache, typed: bool):
    @cache.memoize(typed=typed)
    async def func(a=1, b=2):
        return a, b

    assert await func(b=3) == (1, 3)
    assert await func(3) == (3, 2)
    assert func.cache_key(b=3) != func.cache_key(3)


@parametrize("callable_type", ["method", "object"])
def test_cache_memoize_bound_arg_normalization(cache: Cache, callable_type: str):
    class Callable:
        __name__ = "Callable"

        def __call__(self, a=1, b=2):
            return a, b

    instance = Callable()
    target = instance.__call__ if callable_type == "method" else instance
    func = cache.memoize()(target)

    assert func(1, 2) == (1, 2)
    assert func.cache_key(1, 2) == func.cache_key(a=1, b=2)
    assert func.cache_key(1, 2) == func.cache_key(1, b=2)
    assert func(b=3) == (1, 3)
    assert func(3) == (3, 2)
    assert func.cache_key(b=3) != func.cache_key(3)


def test_cache_memoize_positional_only_keywords(cache: Cache):
    @cache.memoize()
    def func(a=1, /, **kwargs):
        return a, kwargs

    assert func(a=3) == (1, {"a": 3})
    assert func(3) == (3, {})
    assert func.cache_key(a=3) != func.cache_key(3)


def test_cache_memoize_hash_collisions(cache: Cache):
    """Test that cache.memoize() doesn't share results between arguments with the same hash()."""
    assert hash(-1) == hash(-2)

    @cache.memoize()
    def func(a):
        return a

    assert func(-1) == -1
    assert func(-2) == -2
    assert func.cache_key(-1) != func.cache_key(-2)
    assert len(cache) == 2


def test_cache_memoize_custom_hash_collisions(cache: Cache):
    """Test that cache.memoize() distinguishes unequal arguments even if their hashes collide."""

    class Colliding:
        def __init__(self, value: int):
            self.value = value

        def __eq__(self, other: t.Any) -> bool:
            return isinstance(other, Colliding) and self.value == other.value

        def __hash__(self) -> int:
            return 1

    calls = []

    @cache.memoize()
    def func(a):
        calls.append(a.value)
        return a.value

    assert func(Colliding(1)) == 1
    assert func(Colliding(2)) == 2
    assert func(Colliding(1)) == 1
    assert calls == [1, 2]


def test_cache_memoize_unhashable_args(cache: Cache):
    """Test that cache.memoize() keys unhashable arguments by value."""
    calls = []

    @cache.memoize()
    def func(a, b=None):
        calls.append((a, b))
        return len(calls)

    first = func([1, [2, 3]], {"x": {1, 2}})
    assert func([1, [2, 3]], {"x": {2, 1}}) == first
    assert func(a=[1, [2, 3]], b={"x": {1, 2}}) == first
    assert len(calls) == 1

    assert func([1, [2, 4]], {"x": {1, 2}}) != first
    assert len(calls) == 2


def test_cache_memoize_unhashable_container_types(cache: Cache):
    """Test that cache.memoize() doesn't mix up containers of different types that hold equal
    items."""

    @cache.memoize()
    def func(a):
        return a

    values = [[1], (1,), {1}, frozenset({1}), {1: 1}, [(1,)], ([1],), [[1]]]
    keys = {func.cache_key(value) for value in values}

    assert len(keys) == len(values)


def test_cache_memoize_unhashable_args_are_copied(cache: Cache):
    """Test that mutating an unhashable argument after the call doesn't change its cache key."""
    calls = []

    @cache.memoize()
    def func(a):
        calls.append(list(a))
        return len(calls)

    items = [1, 2]
    assert func(items) == 1

    items.append(3)
    assert func(items) == 2
    assert func([1, 2]) == 1
    assert func([1, 2, 3]) == 2
    assert len(calls) == 2


@parametrize("typed", [False, True])
def test_cache_memoize_nested_arg_types(cache: Cache, typed: bool):
    """Test that cache.memoize(typed=True) factors in the types of items nested in containers."""

    @cache.memoize(typed=typed)
    def func(a):
        return a

    for left, right in (((1,), (1.0,)), ([1], [1.0]), ({"a": 1}, {"a": 1.0}), ({1}, {1.0})):
        assert (func.cache_key(left) != func.cache_key(right)) is typed


def test_cache_memoize_unhashable_object_identity(cache: Cache):
    """Test that cache.memoize() falls back to identity for unhashable objects that aren't
    builtin containers."""

    class Unhashable:
        __hash__ = None  # type: ignore[assignment]

        def __eq__(self, other: t.Any) -> bool:
            return True

    calls = []

    @cache.memoize()
    def func(a):
        calls.append(a)
        return len(calls)

    obj = Unhashable()
    assert func(obj) == 1
    assert func(obj) == 1
    assert func(Unhashable()) == 2
    assert len(calls) == 2


def test_cache_memoize_unhashable_object_identity_keeps_object_alive(cache: Cache):
    """Test that an identity cache key holds its object so a recycled id() can't cause a false
    hit."""

    class Unhashable:
        __hash__ = None  # type: ignore[assignment]

    @cache.memoize()
    def func(a):
        return 1

    obj = Unhashable()
    ref = weakref.ref(obj)
    func(obj)
    del obj
    gc.collect()
    assert ref() is not None

    cache.clear()
    gc.collect()
    assert ref() is None


def test_cache_memoize_default_arg_normalization(cache: Cache):
    """Test that cache.memoize() treats omitted arguments the same as passing their defaults."""

    @cache.memoize()
    def func(a, b=2, *args, c=3, **kwargs):
        return a, b, args, c, kwargs

    for args, kwargs in (
        ((1, 2), {}),
        ((1,), {"b": 2}),
        ((1,), {"c": 3}),
        ((1, 2), {"c": 3}),
        ((), {"a": 1, "b": 2, "c": 3}),
    ):
        assert func.cache_key(*args, **kwargs) == func.cache_key(1)

    assert func.cache_key(1, 3) != func.cache_key(1)
    assert func.cache_key(1, c=4) != func.cache_key(1)
    assert func.cache_key(1, 2, 3) != func.cache_key(1)
    assert func.cache_key(1, d=4) != func.cache_key(1)


def test_cache_memoize_kwargs_order(cache: Cache):
    """Test that cache.memoize() ignores the order of extra keyword arguments."""

    @cache.memoize()
    def func(**kwargs):
        return kwargs

    assert func.cache_key(a=1, b=2) == func.cache_key(b=2, a=1)
    assert func.cache_key(a=1, b=2) != func.cache_key(a=1, b=3)


def test_cache_memoize_positional_only_name_in_kwargs(cache: Cache):
    """Test that cache.memoize() accepts a keyword named like a positional-only parameter when
    the function takes **kwargs."""

    @cache.memoize()
    def func(a, /, **kwargs):
        return a, kwargs

    assert func(1, a=2) == (1, {"a": 2})
    assert func.cache_key(1, a=2) != func.cache_key(1)

    with pytest.raises(TypeError):
        func(a=2)  # type: ignore[call-arg]


def test_cache_memoize_invalid_arguments(cache: Cache):
    """Test that cache.memoize() raises TypeError for calls the function wouldn't accept and
    doesn't cache anything."""

    @cache.memoize()
    def func(a):
        return a

    with pytest.raises(TypeError):
        func()  # type: ignore[call-arg]

    with pytest.raises(TypeError):
        func(1, 2)  # type: ignore[call-arg]

    with pytest.raises(TypeError):
        func(b=1)  # type: ignore[call-arg]

    assert len(cache) == 0


def test_cache_memoize_invalidate(cache: Cache):
    """Test that cache.memoize() adds an invalidate() that removes only that function's entries."""
    calls = []

    @cache.memoize()
    def func1(a):
        calls.append(a)
        return a

    @cache.memoize()
    def func2(a):
        return a

    for i in range(3):
        func1(i)
        func2(i)

    cache.set("other", 1)
    cache.set((func1.uncached,), 2)
    assert len(cache) == 8

    assert func1.invalidate() == 3
    assert len(cache) == 5
    assert func1.invalidate() == 0
    assert cache.has("other")
    assert cache.has((func1.uncached,))
    assert all(cache.has(func2.cache_key(i)) for i in range(3))

    func1(0)
    assert calls == [0, 1, 2, 0]


@pytest.mark.asyncio
async def test_cache_memoize_async_unhashable_args(cache: Cache):
    """Test that cache.memoize() keys unhashable arguments by value for async functions."""
    calls = []

    @cache.memoize()
    async def func(a, **kwargs):
        calls.append((a, kwargs))
        return len(calls)

    assert await func([1, 2], b={"c": 1}) == 1
    assert await func([1, 2], b={"c": 1}) == 1
    assert await func([1, 2], b={"c": 2}) == 2


@pytest.mark.parametrize("cache_class", CACHE_CLASSES)
@pytest.mark.parametrize("error_class", [ValueError, KeyError])
def test_cache_delete_callback_error_keeps_bookkeeping_consistent(cache_class, error_class):
    cache = cache_class(timer=lambda: 0, enable_stats=True)
    cache.set("key", "old", ttl=1)
    error = error_class("callback failed")

    def fail(key, value, cause):
        assert (key, value, cause) == ("key", "old", RemovalCause.DELETE)
        raise error

    cache.on_delete = fail
    with pytest.raises(error_class) as caught:
        cache.delete("key")
    assert caught.value is error
    assert cache.copy() == {}
    assert cache.expire_times() == {}
    cache.on_delete = None
    cache.set("new", "value")
    assert cache.popitem() == ("new", "value")


@pytest.mark.parametrize("cache_class", CACHE_CLASSES)
def test_cache_delete_callback_can_replace_key_with_its_own_ttl(cache_class):
    now = [0]
    cache = cache_class(timer=lambda: now[0])
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


@pytest.mark.parametrize("cache_class", CACHE_CLASSES)
@pytest.mark.parametrize("replacement_ttl", [0, 5])
def test_cache_expiration_sweep_preserves_other_key_refreshed_by_callback(
    cache_class, replacement_ttl
):
    now = [0]
    cache = cache_class(timer=lambda: now[0])
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


@pytest.mark.parametrize("cache_class", CACHE_CLASSES)
def test_cache_expiration_sweep_does_not_count_other_key_deleted_by_callback(cache_class):
    now = [0]
    cache = cache_class(timer=lambda: now[0])
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


@pytest.mark.parametrize("cache_class", CACHE_CLASSES)
@pytest.mark.parametrize("operation", ["insert", "replace", "evict"])
def test_cache_failed_expiration_preserves_cache(cache_class, operation):
    cache = cache_class(maxsize=1, timer=lambda: Decimal("9e9"), enable_stats=True)  # type: ignore
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
def test_cache_failed_timer_preserves_cache(replace):
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


@pytest.mark.parametrize("cache_class", CACHE_CLASSES)
@pytest.mark.parametrize("operation", ["get", "has", "add"])
def test_cache_expiration_callback_key_error_propagates(cache_class, operation):
    now = [0]
    cache = cache_class(timer=lambda: now[0], enable_stats=True)
    cache.set("key", "old", ttl=1)
    error = KeyError("callback configuration missing")
    defaults = []
    reads = []
    removals = []

    def default(key):
        defaults.append(key)
        return "default"

    def fail(key, value, cause):
        removals.append((key, value, cause))
        raise error

    cache.default = default
    cache.on_get = lambda *args: reads.append(args)
    cache.on_delete = fail
    now[0] = 1
    with pytest.raises(KeyError) as caught:
        if operation == "get":
            cache.get("key")
        elif operation == "has":
            cache.has("key")
        else:
            cache.add("key", "new")

    assert caught.value is error
    assert removals == [("key", "old", RemovalCause.EXPIRED)]
    assert defaults == []
    assert reads == []
    assert cache.copy() == {}
    assert cache.expire_times() == {}
    assert cache.stats.info().access_count == 0
    if isinstance(cache, LFUCache):
        assert cache._access_counts == {}

    cache.on_delete = None
    cache.set("recovered", "value")
    assert cache.popitem() == ("recovered", "value")


@pytest.mark.parametrize("cache_class", CACHE_CLASSES)
def test_cache_expiration_callback_key_error_preserves_replacement(cache_class):
    now = [0]
    cache = cache_class(timer=lambda: now[0], enable_stats=True)
    cache.set("key", "old", ttl=1)
    error = KeyError("callback failed after replacement")
    defaults = []

    def replace_and_fail(key, value, cause):
        cache.set(key, "replacement", ttl=5)
        raise error

    cache.on_delete = replace_and_fail
    now[0] = 1
    with pytest.raises(KeyError) as caught:
        cache.get("key", default=defaults.append)
    assert caught.value is error
    assert defaults == []
    assert cache.copy() == {"key": "replacement"}
    assert cache.expire_times() == {"key": 6}
    assert cache.stats.info().access_count == 0
    if isinstance(cache, LFUCache):
        assert cache._access_counts == {"key": -1}
    cache.on_delete = None
    assert cache.get("key") == "replacement"


@pytest.mark.parametrize("cache_class", CACHE_CLASSES)
def test_cache_timer_key_error_propagates_without_replacing_cached_value(cache_class):
    cache = cache_class(timer=lambda: 0, enable_stats=True)
    cache.set("key", "old", ttl=5)
    error = KeyError("clock configuration missing")
    defaults = []
    reads = []

    def fail():
        raise error

    cache.configure(timer=fail)
    cache.on_get = lambda *args: reads.append(args)
    with pytest.raises(KeyError) as caught:
        cache.get("key", default=defaults.append)
    assert caught.value is error
    assert defaults == []
    assert reads == []
    assert cache.copy() == {"key": "old"}
    assert cache.expire_times() == {"key": 5}
    assert cache.stats.info().access_count == 0
    if isinstance(cache, LFUCache):
        assert cache._access_counts == {"key": -1}


@pytest.mark.parametrize("cache_class", CACHE_CLASSES)
def test_cache_ordinary_expiration_still_runs_default_and_records_miss(cache_class):
    now = [0]
    cache = cache_class(timer=lambda: now[0], enable_stats=True)
    cache.set("key", "old", ttl=1)
    removals = []
    reads = []
    cache.on_delete = lambda *args: removals.append(args)
    cache.on_get = lambda *args: reads.append(args)
    now[0] = 1
    assert cache.get("key", default=lambda key: "new") == "new"
    assert removals == [("key", "old", RemovalCause.EXPIRED)]
    assert reads == [("key", "new", False)]
    assert cache.copy() == {"key": "new"}
    assert cache.expire_times() == {}
    assert cache.stats.info().miss_count == 1
    assert cache.get("key") == "new"
    assert cache.stats.info().hit_count == 1


@parametrize("typed", [False, True])
def test_cache_memoize_unhashable_callable(cache: Cache, typed: bool):
    @dataclass
    class Offset:
        offset: int
        calls: int = field(default=0, compare=False)

        def __call__(self, value=1):
            self.calls += 1
            return self.offset + value

    target = Offset(10)
    other_target = Offset(10)
    func = cache.memoize(typed=typed)(target)
    other = cache.memoize(typed=typed)(other_target)

    assert func() == 11
    assert func(value=1) == 11
    assert func(2) == 12
    assert target.calls == 2
    assert func.uncached is target
    assert cache.get(func.cache_key(2)) == 12

    # Equal callable instances still own separate cache entries.
    assert target == other_target
    assert func.cache_key() != other.cache_key()
    assert other() == 11
    assert other_target.calls == 1
    assert len(cache) == 3

    assert func.invalidate() == 2
    assert func.invalidate() == 0
    assert cache.has(other.cache_key())
    assert func() == 11
    assert target.calls == 3


@parametrize("typed", [False, True])
def test_cache_memoize_unhashable_callable_shared_invalidation(cache: Cache, typed: bool):
    @dataclass
    class Identity:
        calls: int = field(default=0, compare=False)

        def __call__(self, value):
            self.calls += 1
            return value

    target = Identity()
    first = cache.memoize(typed=typed)(target)
    second = cache.memoize(typed=typed)(target)
    assert first.cache_key(1) == second.cache_key(1)
    assert hash(first.cache_key(1)) == hash(second.cache_key(1))
    assert first(1) == 1
    assert second(value=1) == 1
    assert second(2) == 2
    assert target.calls == 2
    cache.set("unrelated", 3)

    assert first.invalidate() == 2
    assert second.invalidate() == 0
    assert cache.copy() == {"unrelated": 3}


@pytest.mark.asyncio
@parametrize("typed", [False, True])
async def test_cache_memoize_unhashable_async_partial(cache: Cache, typed: bool):
    class UnhashablePartial(partial):
        __hash__ = None  # type: ignore[assignment]

    calls = []

    async def add(left, right):
        calls.append((left, right))
        return left + right

    target = UnhashablePartial(add, 10)
    func = cache.memoize(typed=typed)(target)
    assert await func(2) == 12
    assert await func(right=2) == 12
    assert calls == [(10, 2)]
    assert func.uncached is target
    assert cache.get(func.cache_key(2)) == 12
    assert func.invalidate() == 1
    assert await func(2) == 12
    assert calls == [(10, 2), (10, 2)]


@parametrize("typed", [False, True])
def test_cache_memoize_hashable_callable_keys_unchanged(cache: Cache, typed: bool):
    calls = []

    @dataclass(frozen=True)
    class Offset:
        offset: int

        def __call__(self, value):
            calls.append(self)
            return self.offset + value

    target = Offset(10)
    equal_target = Offset(10)
    first = cache.memoize(typed=typed)(target)
    second = cache.memoize(typed=typed)(equal_target)

    # Hashable callables still appear directly in keys and compare by equality.
    first_key = first.cache_key(1)
    second_key = second.cache_key(1)
    assert isinstance(first_key, tuple)
    assert isinstance(second_key, tuple)
    assert first_key[0] is target
    assert second_key[0] is equal_target
    assert first_key == second_key
    assert first(1) == 11
    assert second(1) == 11
    assert len(calls) == 1
    # Invalidation still matches the original stored callable by identity.
    assert second.invalidate() == 0
    assert first.invalidate() == 1
