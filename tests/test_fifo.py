import inspect

from cacheout import Cache, FIFOCache


def test_fifo_does_not_override_cache_class():
    """Test that FIFOCache doesn't override any methods in Cache."""
    for name, value in inspect.getmembers(FIFOCache):
        if name in (
            "__doc__",
            "__module__",
            "__dict__",
            "__init_subclass__",
            "__subclasshook__",
        ):
            continue
        assert value is getattr(Cache, name)
