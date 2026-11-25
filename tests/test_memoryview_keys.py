import pytest

from cacheout import Cache


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("kind", ["writable", "format", "unhashable_owner"])
def test_memoize_unhashable_memoryview_uses_identity(typed, kind):
    calls = []

    @Cache().memoize(typed=typed)
    def describe(view):
        calls.append(view)
        return view.format, len(view), view.tobytes()

    def make_view():
        if kind == "writable":
            return memoryview(bytearray(b"abcd"))
        if kind == "format":
            return memoryview(b"abcd").cast("H")
        return memoryview(bytearray(b"abcd")).toreadonly()

    first, second = make_view(), make_view()
    expected = describe.uncached(first)
    calls.clear()
    assert describe(first) == expected
    assert describe(first) == expected
    assert describe(second) == expected
    assert len(calls) == 2
    assert describe.cache_key(first) != describe.cache_key(second)
    assert describe.invalidate() == 2


@pytest.mark.parametrize("typed", [False, True])
def test_memoize_hashable_memoryviews_still_share_equal_keys(typed):
    calls = []

    @Cache().memoize(typed=typed)
    def length(view):
        calls.append(view)
        return len(view)

    first, second = memoryview(b"abc"), memoryview(b"abc")
    assert length(first) == length(second) == 3
    assert len(calls) == 1
    assert length.cache_key(first) == length.cache_key(second)


def test_memoize_does_not_hide_value_errors_from_custom_hashes():
    error = ValueError("broken custom hash")

    class BrokenHash:
        def __hash__(self):
            raise error

    @Cache().memoize()
    def identity(value):
        pytest.fail("The original hash failure should propagate before calling the function")

    with pytest.raises(ValueError) as raised:
        identity(BrokenHash())
    assert raised.value is error
