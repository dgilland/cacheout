"""The cache module provides the :class:`Cache` class which is used as the base for all other cache
types."""

import asyncio
from collections import OrderedDict
from decimal import Decimal
import fnmatch
from functools import wraps
import hashlib
import inspect
import re
from threading import RLock
import time


try:
    from re import Pattern
except ImportError:  # pragma: no cover
    from re import _pattern_type as Pattern


_NOTSET = object()


class Cache(object):
    """
    An in-memory, FIFO cache object that supports:

    - Maximum number of cache entries
    - Global TTL default
    - Per cache entry TTL
    - TTL first/non-TTL FIFO cache eviction policy

    Cache entries are stored in an ``OrderedDict`` so that key ordering based on the cache type can
    be maintained without the need for additional list(s). Essentially, the key order of the
    ``OrderedDict`` is treated as an "eviction queue" with the convention that entries at the
    beginning of the queue are "newer" while the entries at the end are "older" (the exact meaning
    of "newer" and "older" will vary between different cache types). When cache entries need to be
    evicted, expired entries are removed first followed by the "older" entries (i.e. the ones at the
    end of the queue).

    Attributes:
        maxsize (int, optional): Maximum size of cache dictionary. Defaults to ``256``.
        ttl (int, optional): Default TTL for all cache entries. Defaults to ``0`` which means that
            entries do not expire.
        timer (callable, optional): Timer function to use to calculate TTL expiration. Defaults to
            ``time.time``.
        default (mixed, optional): Default value or function to use in :meth:`get` when key is not
            found. If callable, it will be passed a single argument, ``key``, and its return value
            will be set for that cache key.
    """

    def __init__(self, maxsize=None, ttl=None, timer=None, default=None):
        if maxsize is None:
            maxsize = 256

        if ttl is None:
            ttl = 0

        if timer is None:
            timer = time.time

        self.setup()
        self.configure(maxsize=maxsize, ttl=ttl, timer=timer, default=default)

    def setup(self):
        self._cache = OrderedDict()
        self._expire_times = {}
        self._lock = RLock()

    def configure(self, maxsize=None, ttl=None, timer=None, default=None):
        """
        Configure cache settings.

        This method is meant to support runtime level configurations for global level cache objects.
        """
        if maxsize is not None:
            if not isinstance(maxsize, int):
                raise TypeError("maxsize must be an integer")

            if not maxsize >= 0:
                raise ValueError("maxsize must be greater than or equal to 0")

            self.maxsize = maxsize

        if ttl is not None:
            if not isinstance(ttl, (int, float, Decimal)):
                raise TypeError("ttl must be a number")

            if not ttl >= 0:
                raise ValueError("ttl must be greater than or equal to 0")

            self.ttl = ttl

        if timer is not None:
            if not callable(timer):
                raise TypeError("timer must be a callable")

            self.timer = timer

        self.default = default

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, list(self.copy().items()))

    def __len__(self):
        with self._lock:
            return len(self._cache)

    def __contains__(self, key):
        with self._lock:
            return key in self._cache

    def __iter__(self):
        yield from self.keys()

    def __next__(self):
        return next(iter(self._cache))

    def copy(self):
        """
        Return a copy of the cache.

        Returns:
            OrderedDict
        """
        with self._lock:
            return self._cache.copy()

    def keys(self):
        """
        Return ``dict_keys`` view of all cache keys.

        Note:
            Cache is copied from the underlying cache storage before returning.

        Returns:
            dict_keys
        """
        return self.copy().keys()

    def values(self):
        """
        Return ``dict_values`` view of all cache values.

        Note:
            Cache is copied from the underlying cache storage before returning.

        Returns:
            dict_values
        """
        return self.copy().values()

    def items(self):
        """
        Return a ``dict_items`` view of cache items.

        Warning:
            Returned data is copied from the cache object, but any modifications to mutable values
            will modify this cache object's data.

        Returns:
            dict_items
        """
        return self.copy().items()

    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._clear()

    def _clear(self):
        self._cache.clear()
        self._expire_times.clear()

    def has(self, key):
        """
        Return whether cache key exists and hasn't expired.

        Returns:
            bool
        """
        with self._lock:
            return self._has(key)

    def _has(self, key):
        # Use get method since it will take care of evicting expired keys.
        return self._get(key, default=_NOTSET) is not _NOTSET

    def size(self):
        """Return number of cache entries."""
        return len(self)

    def full(self):
        """
        Return whether the cache is full or not.

        Returns:
            bool
        """
        if self.maxsize == 0:
            return False
        return len(self) >= self.maxsize

    def get(self, key, default=None):
        """
        Return the cache value for `key` or `default` or ``missing(key)`` if it doesn't exist or has
        expired.

        Args:
            key (mixed): Cache key.
            default (mixed, optional): Value to return if `key` doesn't exist. If any value other
                than ``None``, then it will take precendence over :attr:`missing` and be used as the
                return value. If `default` is callable, it will function like :attr:`missing` and
                its return value will be set for the cache `key`. Defaults to ``None``.

        Returns:
            mixed: The cached value.
        """
        with self._lock:
            return self._get(key, default=default)

    def _get(self, key, default=None):
        try:
            value = self._cache[key]

            if self.expired(key):
                self._delete(key)
                raise KeyError
        except KeyError:
            if default is None:
                default = self.default

            if callable(default):
                value = default(key)
                self._set(key, value)
            else:
                value = default

        return value

    def get_many(self, iteratee, default=None):
        """
        Return many cache values as a ``dict`` of key/value pairs filtered by an `iteratee` that can
        be one of:

        - ``list`` - List of cache keys.
        - ``str`` - Search string that supports Unix shell-style wildcards.
        - ``re.compile()`` - Compiled regular expression.
        - ``function`` - Function that returns whether a key matches. Invoked with
          ``iteratee(key)``.

        Args:
            iteratee (list|str|Pattern|callable): Iteratee to filter by.
            default (mixed, optional): Value to return if key doesn't exist. Defaults to ``None``.

        Returns:
            dict
        """
        with self._lock:
            return {key: self.get(key, default=default) for key in self._filter(iteratee)}

    def add(self, key, value, ttl=None):
        """
        Add cache key/value if it doesn't already exist. Essentially, this method ignores keys that
        exist which leaves the original TTL in tact.

        Note:
            Cache key must be hashable.

        Args:
            key (mixed): Cache key to add.
            value (mixed): Cache value.
            ttl (int, optional): TTL value. Defaults to ``None`` which uses :attr:`ttl`.
        """
        with self._lock:
            self._add(key, value, ttl=ttl)

    def _add(self, key, value, ttl=None):
        if self._has(key):
            return
        self._set(key, value, ttl=ttl)

    def add_many(self, items, ttl=None):
        """
        Add multiple cache keys at once.

        Args:
            items (dict): Mapping of cache key/values to set.
        """
        for key, value in items.items():
            self.add(key, value, ttl=ttl)

    def set(self, key, value, ttl=None):
        """
        Set cache key/value and replace any previously set cache key. If the cache key previous
        existed, setting it will move it to the end of the cache stack which means it would be
        evicted last.

        Note:
            Cache key must be hashable.

        Args:
            key (mixed): Cache key to set.
            value (mixed): Cache value.
            ttl (int, optional): TTL value. Defaults to ``None`` which uses :attr:`ttl`.
        """
        with self._lock:
            self._set(key, value, ttl=ttl)

    def _set(self, key, value, ttl=None):
        if ttl is None:
            ttl = self.ttl

        if key not in self:
            self.evict()

        self._delete(key)
        self._cache[key] = value

        if ttl and ttl > 0:
            self._expire_times[key] = self.timer() + ttl

    def set_many(self, items, ttl=None):
        """
        Set multiple cache keys at once.

        Args:
            items (dict): Mapping of cache key/values to set.
        """
        for key, value in items.items():
            self.set(key, value, ttl=ttl)

    def delete(self, key):
        """
        Delete cache key and return number of entries deleted (``1`` or ``0``).

        Returns:
            int: ``1`` if key was deleted, ``0`` if key didn't exist.
        """
        with self._lock:
            return self._delete(key)

    def _delete(self, key):
        count = 0

        try:
            del self._cache[key]
            count = 1
        except KeyError:
            pass

        try:
            del self._expire_times[key]
        except KeyError:
            pass

        return count

    def delete_many(self, iteratee):
        """
        Delete multiple cache keys at once filtered by an `iteratee` that can be one of:

        - ``list`` - List of cache keys.
        - ``str`` - Search string that supports Unix shell-style wildcards.
        - ``re.compile()`` - Compiled regular expression.
        - ``function`` - Function that returns whether a key matches. Invoked with
          ``iteratee(key)``.

        Args:
            iteratee (list|str|Pattern|callable): Iteratee to filter by.

        Returns:
            int: Number of cache keys deleted.
        """
        count = 0

        with self._lock:
            keys = list(self._filter(iteratee))
            for key in keys:
                count += self.delete(key)

        return count

    def delete_expired(self):
        """
        Delete expired cache keys and return number of entries deleted.

        Returns:
            int: Number of entries deleted.
        """
        with self._lock:
            return self._delete_expired()

    def _delete_expired(self):
        count = 0

        if not self._expire_times:
            return count

        # Use a static expiration time for each key for better consistency as opposed to
        # a newly computed timestamp on each iteration.
        expires_on = self.timer()
        expire_times = self._expire_times.copy()

        for key, expiration in expire_times.items():
            if expiration <= expires_on:
                count += self._delete(key)

        return count

    def expired(self, key, expires_on=None):
        """
        Return whether cache key is expired or not.

        Args:
            key (mixed): Cache key.
            expires_on (float, optional): Timestamp of when the key is considered expired. Defaults
                to ``None`` which uses the current value returned from :meth:`timer`.

        Returns:
            bool
        """
        if not expires_on:
            expires_on = self.timer()

        try:
            return self._expire_times[key] <= expires_on
        except KeyError:
            return key not in self

    def expire_times(self):
        """
        Return cache expirations for TTL keys.

        Returns:
            dict
        """
        with self._lock:
            return self._expire_times.copy()

    def evict(self):
        """
        Perform cache eviction per the cache replacement policy:

        - First, remove **all** expired entries.
        - Then, remove non-TTL entries using the cache replacement policy.

        When removing non-TTL entries, this method will only remove the minimum number of entries to
        reduce the number of entries below :attr:`maxsize`. If :attr:`maxsize` is ``0``, then only
        expired entries will be removed.

        Returns:
            int: Number of cache entries evicted.
        """
        count = self.delete_expired()

        if not self.full():
            return count

        with self._lock:
            while self.full():
                try:
                    self._popitem()
                except KeyError:  # pragma: no cover
                    break
                count += 1

        return count

    def popitem(self):
        """
        Delete and return next cache item, ``(key, value)``, based on cache replacement policy while
        ignoring expiration times (i.e. the selection of the item to pop is based soley on the cache
        key ordering).

        Returns:
            tuple: Two-element tuple of deleted cache ``(key, value)``.
        """
        with self._lock:
            self._delete_expired()
            return self._popitem()

    def _popitem(self):
        try:
            key = next(self)
        except StopIteration:
            raise KeyError("popitem(): cache is empty")

        value = self._cache[key]

        self._delete(key)

        return (key, value)

    def _filter(self, iteratee):
        # By default, we'll filter against cache storage.
        target = self._cache

        if isinstance(iteratee, str):
            filter_by = re.compile(fnmatch.translate(iteratee)).match
        elif isinstance(iteratee, Pattern):
            filter_by = iteratee.match
        elif callable(iteratee):
            filter_by = iteratee
        else:
            # We're assuming that iteratee is now an iterable that we want to filter cache keys by.
            # We can optimize the filtering by making the filter target be the list of keys and
            # checking whether those keys are in the cache. I.e. we'll iterate over the iteratee
            # keys can check if the key is in the cache as opposed to iterating over the cache and
            # checking if a key is in iteratee keys.
            target = iteratee

            def filter_by(key):
                return key in self._cache

        return filter(filter_by, target)

    def memoize(self, *, ttl=None, typed=False):
        """
        Decorator that wraps a function with a memoizing callable and works on both synchronous and
        asynchronous functions.

        Each return value from the function will be cached using the function arguments as the cache
        key. The cache object can be accessed at ``<function>.cache``. The uncached version (i.e.
        the original function) can be accessed at ``<function>.uncached``. Each return value from
        the function will be cached using the function arguments as the cache key.

        Keyword Args:
            ttl (int, optional): TTL value. Defaults to ``None`` which uses :attr:`ttl`.
            typed (bool, optional): Whether to cache arguments of a different type separately. For
                example, ``<function>(1)`` and ``<function>(1.0)`` would be treated differently.
                Defaults to ``False``.
        """
        marker = (object(),)

        def decorator(func):
            prefix = "{}.{}:".format(func.__module__, func.__name__)
            argspec = inspect.getfullargspec(func)

            if asyncio.iscoroutinefunction(func):

                @wraps(func)
                @asyncio.coroutine
                def decorated(*args, **kwargs):
                    key = _make_memoize_key(func, args, kwargs, marker, typed, argspec, prefix)
                    value = self.get(key, default=marker)

                    if value is marker:
                        value = yield from func(*args, **kwargs)
                        self.set(key, value, ttl=ttl)

                    return value

            else:

                @wraps(func)
                def decorated(*args, **kwargs):
                    key = _make_memoize_key(func, args, kwargs, marker, typed, argspec, prefix)
                    value = self.get(key, default=marker)

                    if value is marker:
                        value = func(*args, **kwargs)
                        self.set(key, value, ttl=ttl)

                    return value

            decorated.cache = self
            decorated.uncached = func

            return decorated

        return decorator


def _make_memoize_key(func, args, kwargs, marker, typed, argspec, prefix):
    kwargs = kwargs.copy()
    key_args = (func,)

    # Normalize args by moving positional arguments passed in as keyword arguments from kwargs into
    # args. This is so functions like foo(a, b, c) called with foo(1, b=2, c=3) and foo(1, 2, 3) and
    # foo(1, 2, c=3) will all have the same cache key.
    if kwargs:
        for i, arg in enumerate(argspec.args):
            if arg in kwargs:
                args = args[:i] + (kwargs.pop(arg),) + args[i:]

    if args:
        key_args += args

    if kwargs:
        # Separate args and kwargs with marker to avoid ambiguous cases where args provided might
        # look like some other args+kwargs combo.
        key_args += marker
        key_args += tuple(sorted(kwargs.items()))

    if typed and args:
        key_args += tuple(type(arg) for arg in args)

    if typed and kwargs:
        key_args += tuple(type(val) for _, val in sorted(kwargs.items()))

    # Hash everything in key_args and concatenate into a single byte string.
    raw_key = b"".join(map(lambda v: str(v).encode(), (_hash_value(arg) for arg in key_args)))

    # Combine prefix with md5 hash of raw key so that keys are normalized in length.
    return prefix + hashlib.md5(raw_key).hexdigest()


def _hash_value(value):
    # Prefer to hash value based on Python's hash() function but fallback to repr() if it's
    # unhashable.
    try:
        return hash(value)
    except TypeError:
        return repr(value)
