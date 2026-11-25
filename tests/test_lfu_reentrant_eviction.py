import pytest

from cacheout import LFUCache


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
