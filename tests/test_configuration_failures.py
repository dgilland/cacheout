import pytest

from cacheout import Cache


@pytest.mark.parametrize(
    "options, error",
    [
        ({"maxsize": 1, "ttl": -1}, ValueError),
        ({"maxsize": 1, "ttl": "invalid"}, TypeError),
        ({"maxsize": 1, "ttl": 2, "timer": 1}, TypeError),
        ({"maxsize": 1, "ttl": 2, "default": "new", "enable_stats": "yes"}, TypeError),
    ],
)
def test_failed_configuration_keeps_previous_options_and_entries(options, error):
    def timer():
        return 100

    cache = Cache(maxsize=3, ttl=10, timer=timer, default="old", enable_stats=True)
    cache.set_many({"a": 1, "b": 2})
    before = cache.copy()
    deadlines = cache.expire_times()
    with pytest.raises(error):
        cache.configure(**options)
    assert (cache.maxsize, cache.ttl, cache.timer, cache.default) == (3, 10, timer, "old")
    assert cache.copy() == before
    assert cache.expire_times() == deadlines
    assert cache.stats.is_enabled()
    cache.set("c", 3)
    assert list(cache.keys()) == ["a", "b", "c"]
