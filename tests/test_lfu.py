import pytest

from cacheout import LFUCache


parametrize = pytest.mark.parametrize


@pytest.fixture
def cache() -> LFUCache:
    return LFUCache(maxsize=5)


def test_lfu_eviction(cache: LFUCache):
    """Test that LFUCache evicts least frequently used set entries first."""
    key_counts = [("a", 4), ("b", 3), ("c", 5), ("d", 1), ("e", 2)]

    for key, count in key_counts:
        cache.set(key, key)

        for _ in range(count):
            cache.get(key)

    sorted_key_counts = sorted(key_counts, key=lambda kc: kc[1])
    eviction_order = [kc[0] for kc in sorted_key_counts]
    max_access_count = max([kc[1] for kc in sorted_key_counts])

    for n in range(len(key_counts)):
        cache.set(n, n)

        for _ in range(max_access_count + 1):
            cache.get(n)

        assert cache.full()
        assert eviction_order[n] not in cache

        for key in eviction_order[(n + 1) :]:
            assert key in cache


def test_lfu_get(cache: LFUCache):
    """Test that LFUCache.get() returns cached value."""
    for key, value in cache.items():
        assert cache.get(key) == value


def test_lfu_clear(cache: LFUCache):
    """Test that LFUCache.clear() resets access counts."""
    cache.maxsize = 2

    cache.set(1, 1)
    cache.set(2, 2)

    for _ in range(5):
        cache.get(1)

    cache.set(3, 3)

    assert 2 not in cache

    cache.clear()
    assert len(cache) == 0

    cache.set(1, 1)
    cache.set(2, 2)

    cache.get(2)
    cache.set(3, 3)

    assert 1 not in cache


def test_lfu_maxsize_violation_regression():
    """Test that LFUCache doesn't allow maxsize violation."""
    cache = LFUCache(maxsize=4)

    for _ in range(4):
        cache.add(1, 1)
        cache.add(2, 1)

    for _ in range(3):
        cache.add(3, 1)
        cache.add(4, 1)

    cache.add(5, 1)
    cache.add(6, 1)

    assert list(cache.keys()) == [1, 2, 4, 6]


def test_lfu_has_does_not_increase_access_count(cache: LFUCache):
    """Test that LFUCache.has does not increase access counts to keys."""
    assert not cache.has("a")
    assert not cache._access_counts

    cache.set("a", True)
    assert cache._access_counts["a"] == -1

    assert cache.has("a")
    assert cache._access_counts["a"] == -1


def test_lfu_contains_does_not_increase_access_count(cache: LFUCache):
    """Test that "key in LFUCache" does not increase access counts to keys."""
    assert "a" not in cache
    assert not cache._access_counts

    cache.set("a", True)
    assert cache._access_counts["a"] == -1

    assert "a" in cache
    assert cache._access_counts["a"] == -1


def test_lfu_access_count_using_default_callable():
    cache = LFUCache(default=lambda key: False)
    value = cache.get("a")

    assert value is False
    assert cache._access_counts["a"] == -1


def test_lfu_set_many_respects_maxsize():
    cache = LFUCache(maxsize=2)
    cache.set_many({"a": 1, "b": 2, "c": 3})
    assert list(cache.keys()) == ["b", "c"]
    assert cache.popitem() == ("b", 2)
    assert cache.popitem() == ("c", 3)


def test_lfu_set_many_preserves_eviction_order():
    cache = LFUCache(maxsize=2)
    cache.set("hot", 1)
    cache.get("hot")
    cache.set_many({"cold": 2})
    cache.set("next", 3)
    assert "hot" in cache
    assert "cold" not in cache
    assert "next" in cache


@pytest.mark.parametrize("action", ["delete", "clear", "expire"])
def test_lfu_set_on_set_removal(action):
    def on_set(key, _, __):
        if key != "removed":
            return

        if action == "delete":
            cache.delete(key)
        elif action == "clear":
            cache.clear()
        else:
            nonlocal timer
            timer = 2
            cache.delete_expired()

    timer = 0
    cache = LFUCache(maxsize=1, timer=lambda: timer, on_set=on_set)
    cache.set("removed", 0, ttl=1)
    assert not cache._access_counts
    cache.set("first", 1)
    cache.set("second", 2)
    assert dict(cache.items()) == {"second": 2}
    assert cache.popitem() == ("second", 2)


@pytest.mark.parametrize("action", ["delete", "clear", "expire"])
def test_lfu_add_on_set_removal(action):
    def on_set(key, _, __):
        if key != "removed":
            return

        if action == "delete":
            cache.delete(key)
        elif action == "clear":
            cache.clear()
        else:
            nonlocal timer
            timer = 2
            cache.delete_expired()

    timer = 0
    cache = LFUCache(maxsize=1, timer=lambda: timer, on_set=on_set)
    cache.add("removed", 0, ttl=1)
    assert not cache._access_counts
    cache.set("first", 1)
    cache.set("second", 2)
    assert dict(cache.items()) == {"second": 2}
    assert cache.popitem() == ("second", 2)


def test_lfu_set_on_set_removal_then_error():
    error = RuntimeError("on_set callback failed")

    def on_set(key, _, __):
        if key == "removed":
            cache.delete(key)
            raise error

    cache = LFUCache(maxsize=1, on_set=on_set)
    with pytest.raises(RuntimeError) as raised:
        cache.set("removed", 1)
    assert raised.value is error
    assert not cache._access_counts
    cache.set("next", 2)
    assert cache.popitem() == ("next", 2)


def test_lfu_add_on_set_removal_then_error():
    error = RuntimeError("on_set failed")

    def on_set(key, _, __):
        if key == "removed":
            cache.delete(key)
            raise error

    cache = LFUCache(maxsize=1, on_set=on_set)
    with pytest.raises(RuntimeError) as raised:
        cache.add("removed", 1)
    assert raised.value is error
    assert not cache._access_counts
    cache.set("next", 2)
    assert cache.popitem() == ("next", 2)


def test_lfu_set_on_set_replacement_remains_counted():
    def on_set(key, value, _):
        if value == "original":
            cache.set(key, "replacement")

    cache = LFUCache(maxsize=1, on_set=on_set)
    cache.set("key", "original")
    assert dict(cache.items()) == {"key": "replacement"}
    assert cache._access_counts["key"] == -2
    cache.set("next", "next")
    assert dict(cache.items()) == {"next": "next"}


def test_lfu_add_on_set_replacement_remains_counted():
    def on_set(key, value, _):
        if value == "original":
            cache.set(key, "replacement")

    cache = LFUCache(maxsize=1, on_set=on_set)
    cache.add("key", "original")
    assert dict(cache.items()) == {"key": "replacement"}
    assert cache._access_counts["key"] == -2
    cache.set("next", "next")
    assert dict(cache.items()) == {"next": "next"}


def test_lfu_popitem_removes_ghost_counter():
    cache = LFUCache()
    cache.set("live", 1)
    cache._access_counts["ghost"] = 0

    with pytest.raises(KeyError, match="ghost LFU access counter for missing key: ghost"):
        cache.popitem()


@pytest.mark.parametrize("method", ["set", "add"])
@pytest.mark.parametrize("action", ["delete", "clear", "expire"])
def test_lfu_on_set_removal_does_not_leave_ghost_counter(method, action):
    def on_set(key, value, old_value):
        if key != "removed":
            return
        if action == "delete":
            cache.delete(key)
        elif action == "clear":
            cache.clear()
        else:
            now[0] = 2
            cache.delete_expired()

    now = [0]
    cache = LFUCache(maxsize=1, timer=lambda: now[0], on_set=on_set)
    getattr(cache, method)("removed", 0, ttl=1)
    assert not cache._access_counts
    cache.set("first", 1)
    cache.set("second", 2)
    assert dict(cache.items()) == {"second": 2}
    assert cache.popitem() == ("second", 2)


@pytest.mark.parametrize("method", ["set", "add"])
def test_lfu_on_set_removal_then_error_does_not_leave_ghost_counter(method):
    error = RuntimeError("on_set failed")

    def on_set(key, value, old_value):
        if key == "removed":
            cache.delete(key)
            raise error

    cache = LFUCache(maxsize=1, on_set=on_set)
    with pytest.raises(RuntimeError) as raised:
        getattr(cache, method)("removed", 1)
    assert raised.value is error
    assert not cache._access_counts
    cache.set("next", 2)
    assert cache.popitem() == ("next", 2)


@pytest.mark.parametrize("method", ["set", "add"])
def test_lfu_on_set_replacement_remains_counted(method):
    def on_set(key, value, old_value):
        if value == "original":
            cache.set(key, "replacement")

    cache = LFUCache(maxsize=1, on_set=on_set)
    getattr(cache, method)("key", "original")
    assert dict(cache.items()) == {"key": "replacement"}
    assert cache._access_counts["key"] == -2
    cache.set("next", "next")
    assert dict(cache.items()) == {"next": "next"}


@pytest.mark.parametrize("method", ["set", "add"])
@pytest.mark.parametrize("error_type", [RuntimeError, BaseException])
def test_lfu_on_set_error_preserves_live_entry_eviction(method, error_type):
    error = error_type("on_set failed")

    def on_set(key, value, old_value):
        raise error

    cache = LFUCache(maxsize=1, on_set=on_set)
    with pytest.raises(error_type) as raised:
        getattr(cache, method)("first", 1)
    assert raised.value is error
    assert dict(cache.items()) == {"first": 1}
    assert cache._access_counts["first"] == -1

    cache.on_set = None
    cache.set("second", 2)
    assert dict(cache.items()) == {"second": 2}
    assert cache.popitem() == ("second", 2)


def test_lfu_failed_replacement_retains_one_access_count():
    cache = LFUCache(maxsize=2)
    cache.set("key", "old")
    cache.get("key")
    cache.set("other", 2)
    error = RuntimeError("on_set failed")

    def on_set(key, value, old_value):
        raise error

    cache.on_set = on_set
    with pytest.raises(RuntimeError) as raised:
        cache.set("key", "new")
    assert raised.value is error
    assert cache._access_counts["key"] == -1
    assert cache.get("key") == "new"


@pytest.mark.parametrize("method", ["set", "add"])
def test_lfu_on_set_replacement_then_error_retains_nested_count(method):
    error = RuntimeError("on_set failed")

    def on_set(key, value, old_value):
        if value == "original":
            cache.set(key, "replacement")
            raise error

    cache = LFUCache(maxsize=1, on_set=on_set)
    with pytest.raises(RuntimeError) as raised:
        getattr(cache, method)("key", "original")
    assert raised.value is error
    assert dict(cache.items()) == {"key": "replacement"}
    assert cache._access_counts["key"] == -1
    cache.set("next", 2)
    assert dict(cache.items()) == {"next": 2}


def test_lfu_failed_deadline_does_not_touch_existing_count():
    error = RuntimeError("timer failed")

    def timer():
        raise error

    cache = LFUCache(timer=timer)
    cache.set("key", "old")
    before = cache._access_counts.copy()
    with pytest.raises(RuntimeError) as raised:
        cache.set("key", "new", ttl=1)
    assert raised.value is error
    assert dict(cache.items()) == {"key": "old"}
    assert cache._access_counts == before


@pytest.mark.parametrize("callback", ["on_set", "on_get"])
@pytest.mark.parametrize("error_type", [RuntimeError, BaseException])
def test_lfu_default_error_preserves_live_entry_eviction(callback, error_type):
    error = error_type("callback failed")

    def fail(*args):
        raise error

    cache = LFUCache(maxsize=1, **{callback: fail})
    with pytest.raises(error_type) as raised:
        cache.get("first", default=lambda key: 1)
    assert raised.value is error
    assert dict(cache.items()) == {"first": 1}
    assert cache._access_counts["first"] == -1
    cache.on_set = cache.on_get = None
    cache.set("second", 2)
    assert dict(cache.items()) == {"second": 2}
    assert cache.popitem() == ("second", 2)


def test_lfu_on_get_error_does_not_increment_existing_count():
    cache = LFUCache()
    cache.set("key", 1)
    before = cache._access_counts.copy()
    error = RuntimeError("on_get failed")

    def fail(*args):
        raise error

    cache.on_get = fail
    with pytest.raises(RuntimeError) as raised:
        cache.get("key")
    assert raised.value is error
    assert cache._access_counts == before


@pytest.mark.parametrize("callback", ["on_set", "on_get"])
def test_lfu_default_removal_then_error_does_not_add_count(callback):
    error = RuntimeError("callback failed")

    def remove_and_fail(key, *args):
        cache.delete(key)
        raise error

    cache = LFUCache(**{callback: remove_and_fail})
    with pytest.raises(RuntimeError) as raised:
        cache.get("key", default=lambda key: 1)
    assert raised.value is error
    assert not cache._cache
    assert not cache._access_counts


def test_lfu_default_nested_replacement_then_error_not_counted_twice():
    error = RuntimeError("on_set failed")

    def replace_and_fail(key, value, old_value):
        if value == "original":
            cache.set(key, "replacement")
            raise error

    cache = LFUCache(on_set=replace_and_fail)
    with pytest.raises(RuntimeError) as raised:
        cache.get("key", default=lambda key: "original")
    assert raised.value is error
    assert cache._cache["key"] == "replacement"
    assert cache._access_counts["key"] == -1


@pytest.mark.parametrize("method", ["set", "add", "default"])
@pytest.mark.parametrize("maxsize", [1, 2])
def test_lfu_on_set_nested_write_evicts_live_uncounted_entry(method, maxsize):
    cache = LFUCache(maxsize=maxsize)
    if maxsize == 2:
        cache.set("hot", 0)
        cache.get("hot")
    observed_sizes = []

    def on_set(key, value, old_value):
        if key == "cold":
            cache.set("next", 2)
            observed_sizes.append(len(cache))

    cache.on_set = on_set
    if method == "default":
        assert cache.get("cold", default=lambda key: 1) == 1
    else:
        getattr(cache, method)("cold", 1)

    assert observed_sizes == [maxsize]
    expected = {"next": 2} if maxsize == 1 else {"hot": 0, "next": 2}
    assert dict(cache.items()) == expected
    assert cache.popitem() == ("next", 2)
    if maxsize == 2:
        assert cache.popitem() == ("hot", 0)
    assert len(cache) == 0


@pytest.mark.parametrize("method", ["set", "add", "default"])
def test_lfu_on_set_can_pop_the_just_inserted_entry(method):
    cache = LFUCache(maxsize=1)
    popped = []

    def on_set(key, value, old_value):
        popped.append(cache.popitem())

    cache.on_set = on_set
    if method == "default":
        assert cache.get("entry", default=lambda key: 1) == 1
    else:
        getattr(cache, method)("entry", 1)

    assert popped == [("entry", 1)]
    assert len(cache) == 0
    cache.on_set = None
    cache.set("later", 2)
    assert cache.popitem() == ("later", 2)
