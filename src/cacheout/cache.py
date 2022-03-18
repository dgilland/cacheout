"""The cache module provides the :class:`Cache` class which is used as the base for all other cache
types."""

import asyncio
from collections import OrderedDict
from collections.abc import Mapping
import datetime
from decimal import Decimal
import fnmatch
from functools import wraps
import hashlib
import inspect
import json
import math
import os.path
import re
import shutil
from threading import RLock
import time
import typing as t

from dateutil.relativedelta import relativedelta


F = t.TypeVar("F", bound=t.Callable[..., t.Any])
T_DECORATOR = t.Callable[[F], F]
T_TTL = t.Union[int, float]
T_FILTER = t.Union[str, t.List[t.Hashable], t.Pattern, t.Callable]
UNSET = object()


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
            expire.
        timer: Timer function to use to calculate TTL expiration. Defaults to ``time.time``.
        default: Default value or function to use in :meth:`get` when key is not found. If callable,
            it will be passed a single argument, ``key``, and its return value will be set for that
            cache key.
    """

    _cache: OrderedDict
    _expire_times: t.Dict[t.Hashable, T_TTL]
    _lock: RLock
    _path_persist: str

    def __init__(
        self,
        maxsize: int = 256,
        ttl: T_TTL = 0,
        timer: t.Callable[[], T_TTL] = time.time,
        default: t.Any = None,
    ):
        self.maxsize = maxsize
        self.ttl = ttl
        self.timer = timer
        self.default = default

        self.setup()
        self.configure(maxsize=maxsize, ttl=ttl, timer=timer, default=default)

    def setup(self) -> None:
        self._cache: OrderedDict = OrderedDict()
        self._expire_times: t.Dict[t.Hashable, T_TTL] = {}
        self._lock = RLock()

    def configure(
        self,
        maxsize: t.Optional[int] = None,
        ttl: t.Optional[T_TTL] = None,
        timer: t.Optional[t.Callable[[], T_TTL]] = None,
        default: t.Any = UNSET,
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

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({list(self.copy().items())})"

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

    def get(
        self, key: t.Hashable, default: t.Any = None, path_cache: t.Optional[str] = None
    ) -> t.Any:
        """
        Return the cache value for `key` or `default` or ``missing(key)`` if it doesn't exist or has
        expired.

        Args:
            key: Cache key.
            default: Value to return if `key` doesn't exist. If any value other than ``None``, then
                it will take precedence over :attr:`missing` and be used as the return value. If
                `default` is callable, it will function like :attr:`missing` and its return value
                will be set for the cache `key`. Defaults to ``None``.
            path_cache:

        Returns:
            The cached value.
        """
        with self._lock:
            return self._get(key, default=default, path_cache=path_cache)

    def _get(
        self, key: t.Hashable, default: t.Any = None, path_cache: t.Optional[str] = None
    ) -> t.Any:

        try:
            value = self._cache[key]

            if self.expired(key):
                self._delete(key)
                raise KeyError
        except KeyError:
            try:

                if path_cache is None:
                    raise Exception

                cache_content = json.loads(open(path_cache).read())
                if self.timer() > cache_content["_expire_time"]:
                    raise Exception

                self._expire_times[key] = cache_content["_expire_time"]
                value = cache_content["value"]
                self._set(key, cache_content["value"])

            except Exception:
                if default is None:
                    default = self.default

                if callable(default):
                    value = default(key)
                    self._set(key, value)
                else:
                    value = default

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

        This method ignores keys that exist which leaves the original TTL intact.

        Args:
            key: Cache key to add.
            value: Cache value.
            ttl: TTL value. Defaults to ``None`` which uses :attr:`ttl`.
        """
        with self._lock:
            self._add(key, value, ttl=ttl)

    def _add(self, key: t.Hashable, value: t.Any, ttl: t.Optional[T_TTL] = None) -> None:
        if self._has(key):
            return
        self._set(key, value, ttl=ttl)

    def add_many(self, items: Mapping, ttl: t.Optional[T_TTL] = None) -> None:
        """
        Add multiple cache keys at once.

        Args:
            items: Mapping of cache key/values to set.
            ttl: TTL value. Defaults to ``None`` which uses :attr:`ttl`.
        """
        for key, value in items.items():
            self.add(key, value, ttl=ttl)

    def _persistCache(self, value: t.Any, ttl: T_TTL, path_cache: str) -> None:

        file_content = {
            "_expire_time": self.timer() + ttl,
            "_created_time": self.timer(),
            "value": value,
        }

        with open(path_cache, "w") as fd:
            fd.write(json.dumps(file_content))

    def set(
        self,
        key: t.Hashable,
        value: t.Any,
        ttl: t.Optional[T_TTL] = None,
        path_cache: t.Optional[str] = None,
    ) -> None:
        """
        Set cache key/value and replace any previously set cache key.

        If the cache key previously existed, setting it will move it to the end of the cache stack
        which means it would be evicted last.

        Args:
            key: Cache key to set.
            value: Cache value.
            ttl: TTL value. Defaults to ``None`` which uses :attr:`ttl`.
        """
        with self._lock:
            self._set(key, value, ttl=ttl, path_cache=path_cache)

    def _set(
        self,
        key: t.Hashable,
        value: t.Any,
        ttl: t.Optional[T_TTL] = None,
        path_cache: t.Optional[str] = None,
    ) -> None:
        if ttl is None:
            ttl = self.ttl

        if key not in self._cache:
            self.evict()

        self._delete(key)
        self._cache[key] = value

        if ttl and ttl > 0:
            self._expire_times[key] = self.timer() + ttl

            if path_cache is not None:
                self._persistCache(value, ttl=ttl, path_cache=path_cache)

    def set_many(self, items: t.Mapping, ttl: t.Optional[T_TTL] = None) -> None:
        """
        Set multiple cache keys at once.

        Args:
            items: Mapping of cache key/values to set.
            ttl: TTL value. Defaults to ``None`` which uses :attr:`ttl`.
        """
        with self._lock:
            self._set_many(items, ttl=ttl)

    def _set_many(self, items: t.Mapping, ttl: t.Optional[T_TTL] = None) -> None:
        for key, value in items.items():
            self._set(key, value, ttl=ttl)

    def delete(self, key: t.Hashable) -> int:
        """
        Delete cache key and return number of entries deleted (``1`` or ``0``).

        Args:
            key: Cache key to delete.

        Returns:
            int: ``1`` if key was deleted, ``0`` if key didn't exist.
        """
        with self._lock:
            return self._delete(key)

    def _delete(self, key: t.Hashable) -> int:
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
                count += self._delete(key)
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
        expire_times = self._expire_times.copy()

        for key, expiration in expire_times.items():
            if expiration <= expires_on:
                count += self._delete(key)
        return count

    def expired(self, key: t.Hashable, expires_on: t.Optional[T_TTL] = None) -> bool:
        """
        Return whether cache key is expired or not.

        Args:
            key: Cache key.
            expires_on: Timestamp of when the key is considered expired. Defaults to ``None`` which
                uses the current value returned from :meth:`timer`.
        """
        if not expires_on:
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
                    self._popitem()
                except KeyError:  # pragma: no cover
                    break
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
            return self._popitem()

    def _popitem(self):
        try:
            key = next(self)
        except StopIteration:
            raise KeyError("popitem(): cache is empty")

        value = self._cache[key]
        self._delete(key)

        return key, value

    def _filter_keys(self, iteratee: T_FILTER) -> t.List[t.Hashable]:
        # By default, we'll filter against cache storage.
        target: t.Iterable = self._cache

        if isinstance(iteratee, str):
            filter_by = re.compile(fnmatch.translate(iteratee)).match
        elif isinstance(iteratee, t.Pattern):
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

            def filter_by(key):  # type: ignore
                return key in self._cache

        return [key for key in target if filter_by(key)]

    def _deleteExpiredCacheFiles(self, path_folder: str) -> bool:
        folder_content = os.listdir(path_folder)
        count_content: int = len(folder_content)

        for filename in folder_content:

            file_path = os.path.join(path_folder, filename)
            if os.path.isfile(file_path):
                try:
                    cache_content = json.loads(open(file_path).read())
                    if self.timer() > cache_content["_expire_time"]:
                        os.unlink(file_path)
                        count_content -= 1
                except Exception:
                    count_content -= 1

            elif os.path.isdir(file_path):
                is_folder_deleted = self._deleteExpiredCacheFiles(file_path)
                if is_folder_deleted is True:
                    count_content -= 1

        if count_content == 0:
            shutil.rmtree(path_folder)
            return True

        return False

    def persistedCacheSize(self, scale: str = "Mb") -> dict:

        scale_conversion = {
            "Bytes": 1,
            "Kb": 1000,
            "Mb": 1000000,
        }

        if scale not in scale_conversion:
            raise ValueError(
                f'"scale" must be one of the following values: {scale_conversion.keys()}'
            )

        path_to_cache = self.path_persist
        total_size = 0
        nb_files = 0
        for dirpath, _, filenames in os.walk(path_to_cache):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # skip if it is symbolic link
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
                    nb_files += 1

        return {"size": total_size / scale_conversion[scale], "scale": scale, "nb_files": nb_files}

    @property
    def path_persist(self):
        try:
            return self._path_persist
        except Exception:
            self._path_persist = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
            return self._path_persist

    def purgePersisted(self, option: str = "expired") -> None:
        """
        :param option: full / expired
        :return:
        """

        accepted_options = ("full", "expired")
        if option not in accepted_options:
            raise ValueError(f'"option" must be one of the following values: {accepted_options}')

        if os.path.exists(self.path_persist):
            if option == "full":
                shutil.rmtree(self.path_persist)

            elif option == "expired":
                self._deleteExpiredCacheFiles(self.path_persist)

    def roundTTL(
        self, key_start: str, delta: t.Dict[str, int], now: t.Optional[datetime.datetime] = None
    ) -> T_TTL:
        """
        Rounding the remaining TTL based on a specific period: every month / every day / every hour.

        / every 20 minutes of an hour ...
        :param key_start: Accepted values are 'year', 'month', week, 'day', 'hour', 'minute'
        :param delta: Any parameter for the function relativedelta
        :return: Number of seconds until expiration
        More info on relativedelta (https://dateutil.readthedocs.io/en/stable/relativedelta.html)
        """

        accepted_keys: t.Tuple[str, ...] = ("year", "month", "week", "day", "hour", "minute")
        if key_start not in accepted_keys:
            raise ValueError(f"keyStart must be on of the following values: {accepted_keys}")

        if now is None:
            now = datetime.datetime.now()

        # Init params to always have a correct date with year, month & day
        datetime_params: t.Dict[str, int] = {
            "month": 1,
            "day": 1,
        }

        if key_start == "week":
            datetime_params["year"] = now.year
            weekday = 0
            if "weekday" in delta:
                weekday = delta["weekday"]
                del delta["weekday"]
            time_start: datetime.datetime = datetime.datetime(
                **datetime_params  # type: ignore
            ) + relativedelta(weekday=weekday, weeks=-1)
        else:
            # Preparing the parameters of the datetime to get the beginning of the period.
            # For example, if we want to check every hour (key_start= 'hour'),
            # we need to get the datetime of the beginning of the current hour
            for key in ("year", "month", "day", "hour", "minute"):
                datetime_params[key] = getattr(now, key)
                if key == key_start:
                    break

            # Datetime we count from
            time_start: datetime.datetime = datetime.datetime(**datetime_params)  # type: ignore

        # Elapsed time
        time_diff: datetime.timedelta = now - time_start

        # Custom time delta
        time_delta: datetime.timedelta = (
            time_start + relativedelta(**delta) - time_start  # type: ignore
        )

        time_delta_seconds: float = time_delta.total_seconds()
        delta_coef: int = 1
        if time_delta_seconds > 0:
            """
            Getting the periodic coefficient.
            Example:
                reset the cache every 20 minutes of an hour, and the current time is 2:35.
                The cache will expire in 5 minutes, so coef = 2. coef * 20min - currentMinutes
            """
            delta_coef = math.ceil(time_diff.total_seconds() / time_delta_seconds)

        return int(
            (
                time_start + datetime.timedelta(seconds=delta_coef * time_delta_seconds) - now
            ).total_seconds()
        )

    def _getPathCache(self, key: str) -> str:
        """

        :param key: Cache key with the function name, module and hashed arguments
        :return: Path of the cache file
        """

        # Part0 is the path and part1 is the filename
        # For better indexing, each function has its own cache folder instead
        split_key = key.split(":")

        path_cache = split_key[0].split(".")

        # The main cache folder is in the package directory, so it will be deleted if uninstalled
        path_to_cache = self.path_persist
        if os.path.exists(path_to_cache) is False:
            os.mkdir(path_to_cache)

        final_path = os.path.join(path_to_cache, *path_cache)

        # Creating the folders' architecture if not already existing
        if os.path.exists(final_path) is False:
            sub_path = []
            for folder in path_cache:
                sub_path.append(folder)

                _tmp_path = os.path.join(path_to_cache, *sub_path)
                if os.path.exists(_tmp_path) is False:
                    os.mkdir(_tmp_path)

        return os.path.join(final_path, f"{split_key[-1]}.json")

    def memoize(
        self, *, ttl: t.Optional[T_TTL] = None, typed: bool = False, persist: bool = False
    ) -> T_DECORATOR:
        """
        Decorator that wraps a function with a memoizing callable and works on both synchronous and
        asynchronous functions.

        Each return value from the function will be cached using the function arguments as the cache
        key. The cache object can be accessed at ``<function>.cache``. The uncached version (i.e.
        the original function) can be accessed at ``<function>.uncached``. Each return value from
        the function will be cached using the function arguments as the cache key. Calculate the
        cache key for the provided function arguments for use in other operations of the
        ``<function>.cache`` object using the function accessible at ``<function>.cache_key``

        Keyword Args:
            ttl (int, optional): TTL value. Defaults to ``None`` which uses :attr:`ttl`.
            typed (bool, optional): Whether to cache arguments of a different type separately. For
                example, ``<function>(1)`` and ``<function>(1.0)`` would be treated differently.
                Defaults to ``False``.
        """
        marker = (object(),)

        if persist and ttl is None:
            raise ValueError("ttl must be set when persisting cache")

        def decorator(func):
            prefix = f"{func.__module__}.{func.__name__}:"
            argspec = inspect.getfullargspec(func)

            def cache_key(*args, **kwargs):
                return _make_memoize_key(
                    func, args, kwargs, marker, typed, argspec, prefix, persist
                )

            if asyncio.iscoroutinefunction(func):

                @wraps(func)
                async def decorated(*args, **kwargs):
                    key = cache_key(*args, **kwargs)
                    path_cache = self._getPathCache(key) if persist is True else None

                    value = self.get(key, default=marker, path_cache=path_cache)

                    if value is marker:
                        value = await func(*args, **kwargs)
                        self.set(key, value, ttl=ttl, path_cache=path_cache)

                    return value

            else:

                @wraps(func)
                def decorated(*args, **kwargs):
                    key = cache_key(*args, **kwargs)
                    path_cache = self._getPathCache(key) if persist is True else None

                    value = self.get(key, default=marker, path_cache=path_cache)

                    if value is marker:
                        value = func(*args, **kwargs)
                        self.set(key, value, ttl=ttl, path_cache=path_cache)

                    return value

            decorated.cache = self
            decorated.cache_key = cache_key
            decorated.uncached = func

            return decorated

        return decorator


def _make_memoize_key(
    func: t.Callable,
    args: tuple,
    kwargs: dict,
    marker: tuple,
    typed: bool,
    argspec: inspect.FullArgSpec,
    prefix: str,
    persist: bool,
) -> str:
    kwargs = kwargs.copy()
    key_args: tuple = (func.__name__,)

    # Normalize args by moving positional arguments passed in as keyword arguments from kwargs into
    # args. This is so functions like foo(a, b, c) called with foo(1, b=2, c=3) and foo(1, 2, 3) and
    # foo(1, 2, c=3) will all have the same cache key.
    if kwargs:
        for i, arg in enumerate(argspec.args):
            if arg in kwargs:
                args = args[:i] + (kwargs.pop(arg),) + args[i:]

    if args:
        key_args += tuple(type(arg) if hasattr(arg, "__dict__") else arg for arg in args)

    # if kwargs:
    #     # Separate args and kwargs with marker to avoid ambiguous cases where args provided might
    #     # look like some other args+kwargs combo.
    #     key_args += marker
    #     key_args += tuple(sorted(kwargs.items()))

    if typed and args:
        key_args += tuple(type(arg) for arg in args)

    if typed and kwargs:
        key_args += tuple(type(val) for _, val in sorted(kwargs.items()))

    # Hash everything in key_args and concatenate into a single byte string.
    if persist:
        raw_key = "".join(str(key_arg) for key_arg in key_args)
    else:
        raw_key = "".join(str(_hash_value(key_arg)) for key_arg in key_args)

    # Combine prefix with md5 hash of raw key so that keys are normalized in length.
    return prefix + hashlib.md5(raw_key.encode()).hexdigest()


def _hash_value(value: t.Any) -> t.Union[int, str]:
    # Prefer to hash value based on Python's hash() function but fallback to repr() if unhashable.
    try:
        return hash(value)
    except TypeError:
        return repr(value)
