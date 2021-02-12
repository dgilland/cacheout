"""The manager module provides the :class:`CacheManager` class."""

from threading import RLock
import typing as t

from .cache import Cache


class CacheManager:
    """
    The cache manager provides an interface for accessing multiple caches indexed by name.

    Each named cache is a separate cache instance with its own configuration. Named caches can be
    configured during initialization or later using the :meth:`setup` (bulk configuration) or
    :meth:`configure` (individual configuration) methods.

    Example:

        >>> # Configure bulk caches during initialization
        >>> cacheset = CacheManager({"A": {"maxsize": 100}, "B": {"ttl": 90}})
        >>> assert "A" in cacheset
        >>> assert "B" in cacheset

        >>> # Replace bulk caches after initialization
        >>> class MyCache(Cache): pass
        >>> cacheset.setup({"C": {"cache_class": MyCache}, "D": {}})
        >>> assert "A" not in cacheset
        >>> assert "B" not in cacheset
        >>> assert "C" in cacheset
        >>> assert isinstance(cacheset["C"], MyCache)
        >>> assert "D" in cacheset
        >>> assert isinstance(cacheset["D"], Cache)

        >>> # Configure individual cache after initialization
        >>> cacheset.configure("E", **{"cache_class": MyCache})
        >>> assert isinstance(cacheset["E"], MyCache)

        >>> # Replace a cache entity
        >>> cacheset.register("E", Cache())
        >>> assert isinstance(cacheset["E"], Cache)

        >>> # Access caches
        >>> cacheset["C"].set("key1", "value1")
        >>> cacheset["D"].set("key2", "value2")

    Args:
        settings (dict, optional): A ``dict`` indexed by each cache name that should be created and
            configured. Defaults to ``None`` which doesn't configure anything.
        cache_class (callable, optional): A factory function used when creating a cache.
    """

    def __init__(self, settings: t.Optional[dict] = None, cache_class: t.Type[Cache] = Cache):
        self.cache_class = cache_class
        self._lock = RLock()

        self.setup(settings)

    def setup(self, settings: t.Optional[dict] = None) -> None:
        """
        Set up named cache instances using configuration defined in `settings`.

        The `settings` should contain key/values corresponding to the cache name and its cache
        options, respectively. Named caches are then accessible using index access on the cache
        handler object.

        Warning:
            Calling this method will destroy **all** previously configured named caches and replace
            them with what is defined in `settings`.

        Args:
            settings (dict, optional): A ``dict`` indexed by each cache name that contains the
                options for each named cache.
        """
        self._caches: t.Dict[t.Hashable, Cache] = {}

        if settings is not None:
            if not isinstance(settings, dict):
                raise TypeError("settings must be a dict")

            for name, options in settings.items():
                self.configure(name, **options)

    def configure(self, name: t.Hashable, **options: t.Any) -> None:
        """
        Configure cache identified by `name`.

        Note:
            If no cache has been configured for `name`, then it will be created.

        Args:
            name: Cache name identifier.
            **options: Cache options.
        """
        try:
            cache = self[name]
            cache.configure(**options)
        except KeyError:
            self.register(name, self._create_cache(**options))

    def _create_cache(
        self, cache_class: t.Optional[t.Type[Cache]] = None, **options: t.Any
    ) -> Cache:
        cache_class = cache_class or self.cache_class
        return cache_class(**options)

    def register(self, name: t.Hashable, cache: Cache) -> None:
        """Register a named cache instance."""
        self._caches[name] = cache

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.cache_names()})"

    def __getitem__(self, name: t.Hashable) -> t.Any:
        try:
            return self._caches[name]
        except KeyError:
            raise KeyError(
                f"Cache not configured for {name}. Use 'configure({name!r}, **options)' to"
                " configure it."
            )

    def __iter__(self) -> t.Iterator[t.Tuple[t.Hashable, Cache]]:
        with self._lock:
            caches = self._caches.copy()
        yield from caches.items()

    def __contains__(self, name: t.Hashable) -> bool:
        return name in self._caches

    def cache_names(self) -> t.List[t.Hashable]:
        """Return list of names of cache entities."""
        return list(name for name, _ in self)

    def caches(self) -> t.List[Cache]:
        """Return list of cache instances."""
        return list(cache for _, cache in self)

    def clear_all(self) -> None:
        """Clear all caches."""
        for _, cache in self:
            cache.clear()
