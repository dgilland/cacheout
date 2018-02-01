"""The manager module provides the :class:`CacheManager` class.
"""

from threading import RLock

from .cache import Cache


class CacheManager(object):
    """The cache manager provides an interface for accessing multiple caches
    indexed by name.

    Each named cache is a separate cache instance with its own configuration.
    Named caches can be configured during initialization or later using the
    :meth:`setup` (bulk configuration) or :meth:`configure` (individual
    configuration) methods.

    Example:

        >>> # Configure bulk caches during initialization
        >>> caches = CacheManager({'A': {'maxsize': 100},
        ...                        'B': {'ttl': 90}})
        >>> assert 'A' in caches
        >>> assert 'B' in caches

        >>> # Replace bulk caches after initializtion
        >>> class MyCache(Cache): pass
        >>> caches.setup({'C': {'cache_class': MyCache}, 'D': {}})
        >>> assert 'A' not in caches
        >>> assert 'B' not in caches
        >>> assert 'C' in caches
        >>> assert isinstance(caches['C'], MyCache)
        >>> assert 'D' in caches
        >>> assert isinstance(caches['D'], Cache)

        >>> # Configure individual cache after initializtaion
        >>> caches.configure('E', **{'cache_class': MyCache})
        >>> assert isinstance(caches['E'], MyCache)

        >>> # Replace a cache entity
        >>> caches.register('E', Cache())
        >>> assert isinstance(caches['E'], Cache)

        >>> # Access caches
        >>> caches['C'].set('key1', 'value1')
        >>> caches['D'].set('key2', 'value2')

    Args:
        settings (dict, optional): A ``dict`` indexed by each cache name
            that should be created and configured. Defaults to ``None`` which
            doesn't configure anything.
        cache_class (callable, optional): A factory function used when
            creating
    """
    def __init__(self, settings=None, cache_class=Cache):
        self.cache_class = cache_class
        self._lock = RLock()

        self.setup(settings)

    def setup(self, settings=None):
        """Set up named cache instances using configuration defined in
        `settings`.

        The `settings` should contain key/values corresponding to the cache
        name and its cache options, respectively. Named caches are then
        accessible using index access on the cache handler object.

        Warning:
            Calling this method will destroy **all** previously configured
            named caches and replace them with what is defined in `settings`.

        Args:
            settings (dict, optional): A ``dict`` indexed by each cache name
                that contains the options for each named cache.
        """
        self._caches = {}

        if settings is not None:
            if not isinstance(settings, dict):
                raise TypeError('settings must be a dict')

            for name, options in settings.items():
                self.configure(name, **options)

    def configure(self, name, **options):
        """Configure cache identified by `name`.

        Note:
            If no cache has been configured for `name`, then it will be
            created.

        Keyword Args:
            **options: Cache options.
        """
        try:
            cache = self[name]
            cache.configure(**options)
        except KeyError:
            self.register(name, self._create_cache(**options))

    def _create_cache(self, cache_class=None, **options):
        cache_class = cache_class or self.cache_class
        return cache_class(**options)

    def register(self, name, cache):
        """Register a named cache instance."""
        self._caches[name] = cache

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__,
                               sorted(self.cache_names()))

    def __getitem__(self, name):
        try:
            return self._caches[name]
        except KeyError:
            raise KeyError('Cache not configured for {name}. Use '
                           '"configure({name!r}, **options)" to configure it.'
                           .format(name=name))

    def __iter__(self):
        with self._lock:
            caches = self._caches.copy()

        yield from caches.items()

    def __contains__(self, name):
        return name in self._caches

    def cache_names(self):
        """Return list of names of cache entities.

        Returns:
            list
        """
        return list(name for name, _ in self)

    def caches(self):
        """Return list of cache instances.

        Returns:
            list
        """
        return list(cache for _, cache in self)

    def clear_all(self):
        """Clear all caches."""
        for _, cache in self:
            cache.clear()
