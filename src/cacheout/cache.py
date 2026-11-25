"""The cache module provides the :class:`Cache` class which is used as the base for all other cache
types."""

from collections import OrderedDict
from decimal import Decimal
from enum import Enum, auto
import fnmatch
from functools import partial, wraps
import inspect
import re
from threading import RLock
import time
import typing as t

from .stats import CacheStatsTracker


P = t.ParamSpec("P")
R = t.TypeVar("R")

#: Possible types for TTL (time to live) value.
T_TTL = t.Union[int, float]

#: Possible types that can be used to filter cache keys.
T_FILTER = t.Union[str, t.Sequence[t.Hashable], t.Pattern[str], t.Callable[[t.Hashable], t.Any]]

#: Callback that will be executed when a cache entry is retrieved. It is called with arguments
#: ``(key, value, exists)`` where `key` is the cache key, `value` is the value retrieved (could be
#: the default), and `exists` is whether the cache key exists or not.
T_ON_GET_CALLBACK = t.Optional[t.Callable[[t.Hashable, t.Any, bool], None]]

#: Callback that will be executed when a cache entry is set. It is called with arguments
#: ``(key, new_value, old_value)`` where `key` is the cache key, `new_value` is the value is set,
#: and `old_value` is the value it replaced (if the key didn't exist before, it's :const:`UNSET`).
T_ON_SET_CALLBACK = t.Optional[t.Callable[[t.Hashable, t.Any, t.Any], None]]

#: Callback that will be executed when a cache entry is removed. It is called with arguments
#: ``(key, value, cause)`` where `key` is the cache key, `value` is the cached value at the time of
#: deletion, and `cause` is the reason the key was removed (see :class:`RemovalCause` for enumerated
#: causes).
T_ON_DELETE_CALLBACK = t.Optional[t.Callable[[t.Hashable, t.Any, "RemovalCause"], None]]

#: Sentinel value to indicate that an argument was not set.
UNSET = object()


class MemoizedFunction(t.Protocol[P, R]):
    cache: "Cache"
    cache_key: t.Callable[P, t.Hashable]
    uncached: t.Callable[P, R]
    invalidate: t.Callable[[], int]
    __name__: str

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...


class MemoizedDecorator(t.Protocol):
    def __call__(self, func: t.Callable[P, R]) -> MemoizedFunction[P, R]: ...


#: Memoized decorator type.
T_MEMOIZED_DECORATOR = MemoizedDecorator


class _EmptyCacheError(StopIteration):
    """No entry can be selected for eviction."""


class _MissingCacheKeyError(KeyError):
    """The eviction policy selected a stale key."""


class RemovalCause(Enum):
    """
    An enum to represent the cause for the removal of a cache entry.

    Attributes:
        DELETE: indicates that the cache entry was deleted by delete() or delete_many() explicitly.
        EXPIRED: indicates that the cache entry was removed because it expired.
        FULL: indicates that the cache entry was removed because cache has been full (reached the
            maximum size limit).
        POPITEM: indicates that the cache entry was deleted by popitem().
    """

    DELETE = auto()
    EXPIRED = auto()
    FULL = auto()
    POPITEM = auto()


class Cache:
    """
    An in-memory, FIFO cache object.

    It supports:

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
        maxsize: Maximum size of cache dictionary. Defaults to ``256``.
        ttl: Default TTL for all cache entries. Defaults to ``0`` which means that entries do not
            expire. Time units are determined by ``timer`` function. Default units are in seconds.
        timer: Timer function to use to calculate TTL expiration. Defaults to ``time.time`` where
            TTL units are in seconds.
        default: Default value or function to use in :meth:`get` when key is not found. If callable,
            it will be passed a single argument, ``key``, and its return value will be set for that
            cache key.
        on_get: Callback which will be executed when a cache entry is retrieved.
            See :class:`T_ON_GET_CALLBACK` for details.
        on_set: Callback which will be executed when a cache entry is set.
            See :class:`T_ON_SET_CALLBACK` for details.
        on_delete: Callback which will be executed when a cache entry is removed.
            See :class:`T_ON_DELETE_CALLBACK` for details.
        stats: Cache statistics.
    """

    _cache: OrderedDict[t.Hashable, t.Any]
    _expire_times: t.Dict[t.Hashable, T_TTL]
    _lock: RLock

    def __init__(
        self,
        *,
        maxsize: t.Optional[int] = 256,
        ttl: T_TTL = 0,
        timer: t.Callable[[], T_TTL] = time.time,
        default: t.Any = None,
        enable_stats: bool = False,
        on_get: T_ON_GET_CALLBACK = None,
        on_set: T_ON_SET_CALLBACK = None,
        on_delete: T_ON_DELETE_CALLBACK = None,
    ):
        self.maxsize = maxsize
        self.ttl = ttl
        self.timer = timer
        self.default = default
        self.on_get = on_get
        self.on_set = on_set
        self.on_delete = on_delete
        self.stats = CacheStatsTracker(self, enable=enable_stats)

        self.setup()
        self.configure(
            maxsize=maxsize, ttl=ttl, timer=timer, default=default, enable_stats=enable_stats
        )

    def setup(self) -> None:
        self._cache: OrderedDict = OrderedDict()
        self._expire_times: t.Dict[t.Hashable, T_TTL] = {}
        self._lock = RLock()

    def configure(  # noqa: PLR0912
        self,
        *,
        maxsize: t.Optional[int] = None,
        ttl: t.Optional[T_TTL] = None,
        timer: t.Optional[t.Callable[[], T_TTL]] = None,
        default: t.Any = UNSET,
        enable_stats: t.Any = UNSET,
    ) -> None:
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

        if default is not UNSET:
            self.default = default

        if enable_stats is not UNSET:
            if not isinstance(enable_stats, bool):
                raise TypeError("enable_stats must be a boolean")

            if enable_stats:
                self.stats.enable()
            else:
                self.stats.disable()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={id(self)}, total_entries={len(self)})"

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def __contains__(self, key: t.Hashable) -> bool:
        return self.has(key)

    def __iter__(self) -> t.Iterator[t.Hashable]:
        yield from self.keys()

    def __next__(self) -> t.Hashable:
        return next(iter(self._cache))

    def copy(self) -> OrderedDict:
        """Return a copy of the cache."""
        with self._lock:
            return self._cache.copy()

    def keys(self) -> t.KeysView:
        """
        Return ``dict_keys`` view of all cache keys.

        Note:
            Cache is copied from the underlying cache storage before returning.
        """
        return self.copy().keys()

    def values(self) -> t.ValuesView:
        """
        Return ``dict_values`` view of all cache values.

        Note:
            Cache is copied from the underlying cache storage before returning.
        """
        return self.copy().values()

    def items(self) -> t.ItemsView:
        """
        Return a ``dict_items`` view of cache items.

        Warning:
            Returned data is copied from the cache object, but any modifications to mutable values
            will modify this cache object's data.
        """
        return self.copy().items()

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._clear()

    def _clear(self) -> None:
        self._cache.clear()
        self._expire_times.clear()

    def has(self, key: t.Hashable) -> bool:
        """Return whether cache key exists and hasn't expired."""
        with self._lock:
            return self._has(key)

    def _has(self, key: t.Hashable) -> bool:
        # Use get method since it will take care of evicting expired keys.
        return self._get(key, default=UNSET) is not UNSET

    def size(self) -> int:
        """Return number of cache entries."""
        return len(self)

    def full(self) -> bool:
        """Return whether the cache is full or not."""
        if self.maxsize is None or self.maxsize <= 0:
            return False
        return len(self) >= self.maxsize

    def get(self, key: t.Hashable, default: t.Any = None) -> t.Any:
        """
        Return the cache value for `key` or `default` or ``missing(key)`` if it doesn't exist or has
        expired. Exceptions from the timer or expiration callback propagate without running the
        missing-value default or incrementing hit/miss statistics for the interrupted read.

        Args:
            key: Cache key.
            default: Value to return if `key` doesn't exist. If any value other than ``None``, then
                it will take precedence over :attr:`missing` and be used as the return value. If
                `default` is callable, it will function like :attr:`missing` and its return value
                will be set for the cache `key`. Defaults to ``None``.

        Returns:
            The cached value.
        """
        with self._lock:
            return self._get(key, default=default)

    def _get(self, key: t.Hashable, default: t.Any = None) -> t.Any:
        existed = True
        try:
            value = self._cache[key]
        except KeyError:
            existed = False
        else:
            if self.expired(key):
                self._delete(key, RemovalCause.EXPIRED)
                existed = False
            else:
                self.stats.inc_hit_count()

        if not existed:
            self.stats.inc_miss_count()
            if default is None:
                default = self.default

            if callable(default):
                value = default(key)
                self._set(key, value)
            else:
                value = default

        if self.on_get:
            self.on_get(key, value, existed)

        return value

    def get_many(self, iteratee: T_FILTER) -> dict:
        """
        Return many cache values as a ``dict`` of key/value pairs filtered by an `iteratee`.

        The `iteratee` can be one of:

        - ``list`` - List of cache keys
        - ``str`` - Search string that supports Unix shell-style wildcards
        - ``re.compile()`` - Compiled regular expression
        - ``callable`` - Function that returns whether a key matches. Invoked with ``iteratee(key)``

        Args:
            iteratee: Iteratee to filter by.
        """
        with self._lock:
            return self._get_many(iteratee)

    def _get_many(self, iteratee: T_FILTER) -> dict:
        result = {}
        keys = self._filter_keys(iteratee)
        for key in keys:
            value = self.get(key, default=UNSET)
            if value is not UNSET:
                result[key] = value
        return result

    def add(self, key: t.Hashable, value: t.Any, ttl: t.Optional[T_TTL] = None) -> None:
        """
        Add cache key/value if it doesn't already exist.

        This method ignores keys that exist which leaves the original TTL in tact.

        Args:
            key: Cache key to add.
            value: Cache value.
            ttl: TTL value. Defaults to ``None`` which uses :attr:`ttl`. Time units are determined
                by :attr:`timer`.
        """
        with self._lock:
            self._add(key, value, ttl=ttl)

    def _add(self, key: t.Hashable, value: t.Any, ttl: t.Optional[T_TTL] = None) -> None:
        if self._has(key):
            return
        self._set(key, value, ttl=ttl)

    def add_many(self, items: t.Mapping, ttl: t.Optional[T_TTL] = None) -> None:
        """
        Add multiple cache keys at once.

        Args:
            items: Mapping of cache key/values to set.
            ttl: TTL value. Defaults to ``None`` which uses :attr:`ttl`. Time units are determined
                by :attr:`timer`.
        """
        for key, value in items.items():
            self.add(key, value, ttl=ttl)

    def set(self, key: t.Hashable, value: t.Any, ttl: t.Optional[T_TTL] = None) -> None:
        """
        Set cache key/value and replace any previously set cache key.

        If the cache key previously existed, setting it will move it to the end of the cache stack
        which means it would be evicted last. If calculating the expiration raises an exception,
        the existing entries and their expiration times are left unchanged.

        Args:
            key: Cache key to set.
            value: Cache value.
            ttl: TTL value. Defaults to ``None`` which uses :attr:`ttl`. Time units are determined
                by :attr:`timer`.
        """
        with self._lock:
            self._set(key, value, ttl=ttl)

    def _set(self, key: t.Hashable, value: t.Any, ttl: t.Optional[T_TTL] = None) -> None:
        if ttl is None:
            ttl = self.ttl

        # Calculate the deadline before replacing or evicting any existing entries.
        expire_time = self.timer() + ttl if ttl and ttl > 0 else None

        old_value = UNSET
        if key not in self._cache:
            self.evict()
        else:
            old_value = self._cache[key]

        # Delete key before setting it so that it moves to the end of the OrderedDict key list.
        # Needed for cache strategies that rely on the ordering of when keys were last inserted.
        self._delete(key)
        self._cache[key] = value

        if expire_time is not None:
            self._expire_times[key] = expire_time

        if self.on_set:
            self.on_set(key, value, old_value)

    def set_many(self, items: t.Mapping, ttl: t.Optional[T_TTL] = None) -> None:
        """
        Set multiple cache keys at once.

        Args:
            items: Mapping of cache key/values to set.
            ttl: TTL value. Defaults to ``None`` which uses :attr:`ttl`. Time units are determined
                by :attr:`timer`.
        """
        with self._lock:
            self._set_many(items, ttl=ttl)

    def _set_many(self, items: t.Mapping, ttl: t.Optional[T_TTL] = None) -> None:
        for key, value in items.items():
            self.set(key, value, ttl=ttl)

    def delete(self, key: t.Hashable) -> int:
        """
        Delete cache key and return number of entries deleted (``1`` or ``0``).

        Args:
            key: Cache key to delete.

        Returns:
            int: ``1`` if key was deleted, ``0`` if key didn't exist.
        """
        with self._lock:
            return self._delete(key, RemovalCause.DELETE)

    def _delete(self, key: t.Hashable, cause: t.Optional[RemovalCause] = None) -> int:
        """
        Delete cache key and return number of entries deleted (``1`` or ``0``).

        If cause is ``None``, on-delete callback won't be executed.
        Removal bookkeeping is complete before the callback runs, even if
        the callback raises or inserts a replacement for the removed key.
        """
        try:
            value = self._cache.pop(key)
        except KeyError:
            self._expire_times.pop(key, None)
            return 0

        self._expire_times.pop(key, None)
        if cause == RemovalCause.FULL:
            self.stats.inc_eviction_count()
        if cause and self.on_delete:
            self.on_delete(key, value, cause)
        return 1

    def delete_many(self, iteratee: T_FILTER) -> int:
        """
        Delete multiple cache keys at once filtered by an `iteratee`.

        The `iteratee` can be one of:

        - ``list`` - List of cache keys.
        - ``str`` - Search string that supports Unix shell-style wildcards.
        - ``re.compile()`` - Compiled regular expression.
        - ``function`` - Function that returns whether a key matches. Invoked with
          ``iteratee(key)``.

        Args:
            iteratee: Iteratee to filter by.

        Returns:
            int: Number of cache keys deleted.
        """
        with self._lock:
            return self._delete_many(iteratee)

    def _delete_many(self, iteratee: T_FILTER) -> int:
        count = 0
        with self._lock:
            keys = self._filter_keys(iteratee)
            for key in keys:
                count += self._delete(key, RemovalCause.DELETE)
        return count

    def delete_expired(self) -> int:
        """
        Delete expired cache keys and return number of entries deleted.

        Returns:
            int: Number of entries deleted.
        """
        with self._lock:
            return self._delete_expired()

    def _delete_expired(self) -> int:
        if not self._expire_times:
            return 0

        # Use a static expiration time for each key for better consistency as opposed to
        # a newly computed timestamp on each iteration.
        count = 0
        expires_on = self.timer()
        keys = list(self._expire_times)

        for key in keys:
            # An earlier deletion callback may have refreshed this entry.
            if self.expired(key, expires_on=expires_on):
                count += self._delete(key, RemovalCause.EXPIRED)
        return count

    def expire(self, key: t.Hashable, ttl: T_TTL) -> bool:
        """
        Update the TTL of an existing, unexpired cache entry.

        The value, eviction order, access counts, and hit/miss statistics are unchanged. This does
        not call :attr:`on_get` or :attr:`on_set`. An already expired entry is removed, calling
        :attr:`on_delete` with :attr:`RemovalCause.EXPIRED`, and is not revived. Exceptions from
        the timer or deadline calculation leave the entry and its expiration unchanged.

        Args:
            key: Cache key to update.
            ttl: New TTL measured from the current :attr:`timer` value. As with :meth:`set`, zero
                or negative values disable expiration. This does not change the default :attr:`ttl`.

        Returns:
            ``True`` if the entry was updated, or ``False`` if it was missing or had expired.
        """
        with self._lock:
            if key not in self._cache:
                return False

            now = self.timer()
            if self.expired(key, expires_on=now):
                self._delete(key, RemovalCause.EXPIRED)
                return False

            expire_time = now + ttl if ttl and ttl > 0 else None
            if expire_time is None:
                self._expire_times.pop(key, None)
            else:
                self._expire_times[key] = expire_time
            return True

    def expired(self, key: t.Hashable, expires_on: t.Optional[T_TTL] = None) -> bool:
        """
        Return whether cache key is expired or not.

        Args:
            key: Cache key.
            expires_on: Timestamp of when the key is considered expired. Defaults to ``None`` which
                uses the current value returned from :meth:`timer`.
        """
        if expires_on is None:
            expires_on = self.timer()

        try:
            return self._expire_times[key] <= expires_on
        except KeyError:
            return key not in self._cache

    def expire_times(self) -> t.Dict[t.Hashable, T_TTL]:
        """
        Return cache expirations for TTL keys.

        Returns:
            dict
        """
        with self._lock:
            return self._expire_times.copy()

    def get_ttl(self, key: t.Hashable) -> t.Optional[T_TTL]:
        """
        Return the remaining time to live of a key that has a TTL.

        Args:
            key: Cache key.

        Returns:
            The remaining time to live of `key` or ``None`` if the key doesn't exist or has expired.
        """
        with self._lock:
            if not self._has(key):
                return None

            expire_time = self._expire_times.copy().get(key)
            if expire_time is None:
                return None

            ttl = expire_time - self.timer()
            if ttl <= 0:
                self._delete(key, RemovalCause.EXPIRED)
                return None
            return ttl

    def evict(self) -> int:
        """
        Perform cache eviction per the cache replacement policy:

        - First, remove **all** expired entries.
        - Then, remove non-TTL entries using the cache replacement policy.

        When removing non-TTL entries, this method will only remove the minimum number of entries to
        reduce the number of entries below :attr:`maxsize`. If :attr:`maxsize` is ``0``, then only
        expired entries will be removed.

        Returns:
            Number of cache entries evicted.
        """
        count = self.delete_expired()

        if not self.full():
            return count

        with self._lock:
            while self.full():
                try:
                    self._popitem(RemovalCause.FULL)
                except _EmptyCacheError:  # pragma: no cover
                    break
                except _MissingCacheKeyError:  # pragma: no cover
                    pass
                else:
                    count += 1

        return count

    def popitem(self) -> t.Tuple[t.Hashable, t.Any]:
        """
        Delete and return next cache item, ``(key, value)``, based on cache replacement policy while
        ignoring expiration times (i.e. the selection of the item to pop is based solely on the
        cache key ordering).

        Returns:
            Two-element tuple of deleted cache ``(key, value)``.
        """
        with self._lock:
            self._delete_expired()
            return self._popitem(RemovalCause.POPITEM)

    def _popitem(self, cause: RemovalCause):
        try:
            key = next(self)
        except StopIteration as exc:
            raise _EmptyCacheError("popitem(): cache is empty") from exc

        try:
            value = self._cache[key]
        except KeyError as exc:
            from .lfu import LFUCache  # noqa: PLC0415

            if isinstance(self, LFUCache):
                self._access_counts.pop(key, None)
                raise _MissingCacheKeyError(
                    f"ghost LFU access counter for missing key: {key}"
                ) from exc
            raise  # pragma: no cover

        self._delete(key, cause)

        return key, value

    def _filter_keys(self, iteratee: T_FILTER) -> t.List[t.Hashable]:
        target: t.Iterable[t.Hashable] = self._cache
        filter_by: t.Callable[[t.Hashable], bool]

        if isinstance(iteratee, str):
            pattern = re.compile(fnmatch.translate(iteratee))

            def filter_by(key: t.Hashable) -> bool:
                return isinstance(key, str) and pattern.match(key) is not None

        elif isinstance(iteratee, t.Pattern):

            def filter_by(key: t.Hashable) -> bool:
                return isinstance(key, str) and iteratee.match(key) is not None

        elif callable(iteratee):
            # A predicate can read an LRU entry or otherwise mutate the cache.
            target = list(self._cache)
            filter_by = iteratee
        else:
            target = iteratee

            def filter_by(key: t.Hashable) -> bool:
                return key in self._cache

        return [key for key in target if filter_by(key)]

    def memoize(
        self, *, ttl: t.Optional[T_TTL] = None, typed: bool = False
    ) -> T_MEMOIZED_DECORATOR:
        """
        Decorator that wraps a function with a memoizing callable and works on both synchronous and
        asynchronous functions, including callable objects with an asynchronous ``__call__``.

        Each return value from the function will be cached using the function arguments as the cache
        key. The cache object can be accessed at ``<function>.cache``. The uncached version (i.e.
        the original function) can be accessed at ``<function>.uncached``. Each return value from
        the function will be cached using the function arguments as the cache key. Calculate the
        cache key for the provided function arguments for use in other operations of the
        ``<function>.cache`` object using the function accessible at ``<function>.cache_key``

        Type annotations preserve the wrapped function's parameters and return type, including
        for ``uncached``. The ``cache_key`` helper accepts the same parameters and returns the
        hashable cache key. Keys are tuples compared by equality, so distinct arguments can't
        collide. Unhashable arguments are frozen structurally (lists, tuples, dicts, sets) or
        matched by identity as a last resort. ``<function>.invalidate()`` deletes every cache entry
        for the function and returns the number of entries removed. Unhashable callable objects
        are keyed by identity, so equal but distinct instances have separate cache entries.

        Keyword Args:
            ttl: TTL value. Defaults to ``None`` which uses :attr:`ttl`. Time units
                are determined by :attr:`timer`.
            typed: Whether to cache arguments of a different type separately. For
                example, ``<function>(1)`` and ``<function>(1.0)`` would be treated differently.
                Defaults to ``False``.
        """
        marker = object()

        def decorator(func: t.Callable[P, R]) -> MemoizedFunction[P, R]:
            # Preserve hashable callable keys and retain unhashable callables by identity.
            func_key = func if _is_hashable(func) else _Identity(func)
            try:
                signature = inspect.signature(func, follow_wrapped=False)
            except (TypeError, ValueError):
                # Some C callables (e.g. max) do not expose a signature.
                signature = inspect.Signature(
                    [
                        inspect.Parameter("args", inspect.Parameter.VAR_POSITIONAL),
                        inspect.Parameter("kwargs", inspect.Parameter.VAR_KEYWORD),
                    ]
                )
            params = signature.parameters.values()
            posonly = tuple(p.name for p in params if p.kind is inspect.Parameter.POSITIONAL_ONLY)
            varkw = next((p.name for p in params if p.kind is inspect.Parameter.VAR_KEYWORD), None)

            def cache_key(*args, **kwargs):
                return _make_memoize_key(func_key, signature, posonly, varkw, args, kwargs, typed)

            def invalidate() -> int:
                return self.delete_many(
                    lambda key: (
                        isinstance(key, tuple)
                        and len(key) == 2
                        and (
                            key[0] is func
                            or (isinstance(key[0], _Identity) and key[0].obj is func)
                            or (
                                inspect.ismethod(func)
                                and inspect.ismethod(key[0])
                                and key[0].__self__ is func.__self__
                                and key[0].__func__ is func.__func__
                            )
                        )
                    )
                )

            target: t.Any = func
            while isinstance(target, partial):
                target = target.func
            is_async = inspect.iscoroutinefunction(target) or (
                not inspect.isclass(target) and inspect.iscoroutinefunction(target.__call__)
            )

            if is_async:

                @wraps(func)
                async def decorated(*args, **kwargs):
                    key = cache_key(*args, **kwargs)
                    value = self.get(key, default=marker)

                    if value is marker:
                        value = await func(*args, **kwargs)  # type: ignore
                        self.set(key, value, ttl=ttl)

                    return value
            else:

                @wraps(func)
                def decorated(*args, **kwargs):
                    key = cache_key(*args, **kwargs)
                    value = self.get(key, default=marker)

                    if value is marker:
                        value = func(*args, **kwargs)  # type: ignore
                        self.set(key, value, ttl=ttl)

                    return value

            memo = t.cast(MemoizedFunction[P, R], decorated)
            memo.cache = self
            memo.cache_key = cache_key
            memo.uncached = func
            memo.invalidate = invalidate

            return memo

        return decorator


# Unique tags so frozen containers can't equal user data (e.g. [1] vs (1,) vs a literal tuple).
_LIST, _TUPLE, _DICT, _SET, _ORDERED_DICT = (object() for _ in range(5))


class _Identity:
    """Key wrapper for unhashable objects: equal only to itself, by identity."""

    __slots__ = ("obj",)

    def __init__(self, obj: t.Any) -> None:
        self.obj = obj  # strong ref keeps obj alive so its id() can't be reused

    def __eq__(self, other: t.Any) -> bool:
        return isinstance(other, _Identity) and self.obj is other.obj

    def __hash__(self) -> int:
        return id(self.obj)


def _make_memoize_key(  # noqa: PLR0917
    func: t.Hashable,
    signature: inspect.Signature,
    posonly: t.Tuple[str, ...],
    varkw: t.Optional[str],
    args: tuple,
    kwargs: dict[str, t.Any],
    typed: bool,
) -> t.Hashable:
    # bind() rejects a keyword named like an omitted positional-only parameter even when **kwargs
    # accepts it (e.g. f(a=3) for f(a=1, /, **kw)), so set those aside and merge them back below.
    extra: dict[str, t.Any] = {}
    if varkw and posonly:
        kwargs = kwargs.copy()
        extra = {name: kwargs.pop(name) for name in posonly[len(args) :] if name in kwargs}

    # Binding normalizes foo(1, 2), foo(1, b=2) and omitted defaults to the same key.
    bound = signature.bind(*args, **kwargs)
    bound.apply_defaults()

    if extra and varkw:
        bound.arguments[varkw] = {**bound.arguments[varkw], **extra}

    # Argument order is fixed by the signature, so values alone identify the call.
    # Keep modes separate: a typed scalar tag can equal an untyped literal tuple.
    return func, (typed, tuple(_freeze(value, typed) for value in bound.arguments.values()))


def _is_hashable(value: t.Any) -> bool:
    try:
        hash(value)
    except TypeError:
        return False
    return True


def _freeze(value: t.Any, typed: bool, active: t.Optional[set[int]] = None) -> t.Hashable:
    """Return an equality-preserving hashable stand-in for value (copies mutable containers)."""
    if active is None:
        active = set()
    if id(value) in active:
        # Keep only the recursive edge by identity; other fields remain structural.
        frozen = _Identity(value)
        return (type(value), frozen) if typed else frozen
    active.add(id(value))
    try:
        return _freeze_value(value, typed, active)
    finally:
        active.remove(id(value))


def _freeze_value(value: t.Any, typed: bool, active: set[int]) -> t.Hashable:
    hashable = _is_hashable(value)

    if isinstance(value, tuple) and (typed or not hashable):
        frozen: t.Hashable = (_TUPLE, tuple(_freeze(v, typed, active) for v in value))
    elif isinstance(value, frozenset) and typed:
        frozen = (_SET, frozenset(_freeze(v, typed, active) for v in value))
    elif hashable:
        frozen = value
    elif isinstance(value, list):
        frozen = (_LIST, tuple(_freeze(v, typed, active) for v in value))
    elif isinstance(value, OrderedDict):
        frozen = (
            _ORDERED_DICT,
            tuple((_freeze(k, typed, active), _freeze(v, typed, active)) for k, v in value.items()),
        )
    elif isinstance(value, dict):
        frozen = (
            _DICT,
            frozenset(
                (_freeze(k, typed, active), _freeze(v, typed, active)) for k, v in value.items()
            ),
        )
    elif isinstance(value, set):
        frozen = (_SET, frozenset(_freeze(v, typed, active) for v in value))
    else:
        frozen = _Identity(value)

    return (type(value), frozen) if typed else frozen
