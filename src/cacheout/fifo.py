"""
The fifo module provides the :class:`FIFOCache` (First-In, First-Out) class.

Note:
    The :class:`FIOCache` is an alias to :class:`.Cache` since :class:`.Cache` implements FIFO. It
    is provided as a standard name based on its cache replacement policy.
"""

from .cache import Cache


class FIFOCache(Cache):
    """
    The First In, First Out (FIFO) cache is an alias of :class:`.Cache` since :class:`.Cache`
    implements FIFO.

    It is provided as a standard name based on its cache replacement policy.
    """

    pass
