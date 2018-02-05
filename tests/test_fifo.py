
from cacheout import Cache, FIFOCache


def test_fifo_is_alias_of_cache():
    """Test that FIFOCache is an alias of Cache."""
    assert FIFOCache is Cache
