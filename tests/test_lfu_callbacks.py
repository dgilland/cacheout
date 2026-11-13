import pytest

from cacheout import LFUCache


@pytest.mark.parametrize("method", ["set", "add"])
@pytest.mark.parametrize("action", ["delete", "clear", "expire"])
def test_on_set_removal_does_not_leave_ghost_counter(method, action):
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
def test_on_set_removal_then_error_does_not_leave_ghost_counter(method):
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
def test_on_set_replacement_remains_counted(method):
    def on_set(key, value, old_value):
        if value == "original":
            cache.set(key, "replacement")

    cache = LFUCache(maxsize=1, on_set=on_set)
    getattr(cache, method)("key", "original")
    assert dict(cache.items()) == {"key": "replacement"}
    assert cache._access_counts["key"] == -2
    cache.set("next", "next")
    assert dict(cache.items()) == {"next": "next"}
