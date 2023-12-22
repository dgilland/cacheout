cacheout
********

|version| |build| |coveralls| |license|


A caching library for Python.


Links
=====

- Project: https://github.com/dgilland/cacheout
- Documentation: https://cacheout.readthedocs.io
- PyPI: https://pypi.python.org/pypi/cacheout/
- Github Actions: https://github.com/dgilland/cacheout/actions


Features
========

- In-memory caching using dictionary backend
- Cache manager for easily accessing multiple cache objects
- Reconfigurable cache settings for runtime setup when using module-level cache objects
- Maximum cache size enforcement
- Default cache TTL (time-to-live) as well as custom TTLs per cache entry
- Bulk set, get, and delete operations
- Bulk get and delete operations filtered by string, regex, or function
- Memoization decorators
- Thread safe
- Multiple cache implementations:

  - FIFO (First In, First Out)
  - LIFO (Last In, First Out)
  - LRU (Least Recently Used)
  - MRU (Most Recently Used)
  - LFU (Least Frequently Used)
  - RR (Random Replacement)


Roadmap
=======

- Layered caching (multi-level caching)


Requirements
============

- Python >= 3.7


Quickstart
==========

Install using pip:


::

    pip install cacheout


Let's start with some basic caching by creating a cache object:

.. code-block:: python

    from cacheout import Cache

    cache = Cache()


By default the ``cache`` object will have a maximum size of ``256``, default TTL (time-to-live) expiration turned off, TTL timer that uses ``time.time`` (meaning TTL is in seconds), and the default for missing keys as ``None``. These values can be set with:

.. code-block:: python

    cache = Cache(maxsize=256, ttl=0, timer=time.time, default=None)  # defaults


Set a cache key using ``cache.set()``:

.. code-block:: python

    cache.set(1, 'foobar')


Get the value of a cache key with ``cache.get()``:

.. code-block:: python

    assert cache.get(1) == 'foobar'


Get a default value when cache key isn't set:

.. code-block:: python

    assert cache.get(2) is None
    assert cache.get(2, default=False) is False
    assert 2 not in cache


Provide cache values using a default callable:

.. code-block:: python

    assert 2 not in cache
    assert cache.get(2, default=lambda key: key) == 2
    assert cache.get(2) == 2
    assert 2 in cache


Provide a global default:

.. code-block:: python

    cache2 = Cache(default=True)
    assert cache2.get('missing') is True
    assert 'missing' not in cache2

    cache3 = Cache(default=lambda key: key)
    assert cache3.get('missing') == 'missing'
    assert 'missing' in cache3


Set the TTL (time-to-live) expiration per entry (default TTL units are in seconds when ``Cache.timer`` is set to the default ``time.time``; otherwise, the units are determined by the custom timer function):

.. code-block:: python

    cache.set(3, {'data': {}}, ttl=1)
    assert cache.get(3) == {'data': {}}
    time.sleep(1)
    assert cache.get(3) is None


Memoize a function where cache keys are generated from the called function parameters:

.. code-block:: python

    @cache.memoize()
    def func(a, b):
        pass


Provide a TTL for the memoized function and incorporate argument types into generated cache keys:

.. code-block:: python

    @cache.memoize(ttl=5, typed=True)
    def func(a, b):
        pass

    # func(1, 2) has different cache key than func(1.0, 2.0), whereas,
    # with "typed=False" (the default), they would have the same key


Access the original memoized function:

.. code-block:: python

    @cache.memoize()
    def func(a, b):
        pass

    func.uncached(1, 2)


Get a copy of the entire cache with ``cache.copy()``:

.. code-block:: python

    assert cache.copy() == {1: 'foobar', 2: ('foo', 'bar', 'baz')}


Delete a cache key with ``cache.delete()``:

.. code-block:: python

    cache.delete(1)
    assert cache.get(1) is None


Clear the entire cache with ``cache.clear()``:

.. code-block:: python

    cache.clear()
    assert len(cache) == 0


Perform bulk operations with ``cache.set_many()``, ``cache.get_many()``, and ``cache.delete_many()``:

.. code-block:: python

    cache.set_many({'a': 1, 'b': 2, 'c': 3})
    assert cache.get_many(['a', 'b', 'c']) == {'a': 1, 'b': 2, 'c': 3}
    cache.delete_many(['a', 'b', 'c'])
    assert cache.count() == 0


Use complex filtering in ``cache.get_many()`` and ``cache.delete_many()``:

.. code-block:: python

    import re
    cache.set_many({'a_1': 1, 'a_2': 2, '123': 3, 'b': 4})

    cache.get_many('a_*') == {'a_1': 1, 'a_2': 2}
    cache.get_many(re.compile(r'\d')) == {'123': 3}
    cache.get_many(lambda key: '2' in key) == {'a_2': 2, '123': 3}

    cache.delete_many('a_*')
    assert dict(cache.items()) == {'123': 3, 'b': 4}


Reconfigure the cache object after creation with ``cache.configure()``:

.. code-block:: python

    cache.configure(maxsize=1000, ttl=5 * 60)


Get keys, values, and items from the cache with ``cache.keys()``, ``cache.values()``, and ``cache.items()``:

.. code-block:: python

    cache.set_many({'a': 1, 'b': 2, 'c': 3})
    assert list(cache.keys()) == ['a', 'b', 'c']
    assert list(cache.values()) == [1, 2, 3]
    assert list(cache.items()) == [('a', 1), ('b', 2), ('c', 3)]


Iterate over cache keys:

.. code-block:: python

    for key in cache:
        print(key, cache.get(key))
        # 'a' 1
        # 'b' 2
        # 'c' 3


Check if key exists with ``cache.has()`` and ``key in cache``:

.. code-block:: python

    assert cache.has('a')
    assert 'a' in cache


Use callbacks to be notified of on-get, on-set, and on-delete events:

.. code-block:: python

    def on_get(key, value, exists):
        pass

    def on_set(key, new_value, old_value):
        pass

    def on_delete(key, value, cause):
        pass


Enable cache statistics:

.. code-block:: python

    cache_with_stats = Cache(enable_stats=True)

    # Or via configure()
    cache.configure(enable_stats=True)

    # Or directly via Cache.stats
    cache.stats.enable()


Get cache statistics:

.. code-block:: python

    print(cache.stats.info())


Manage tracking of statistics:

.. code-block:: python

    # Pause tracking (collected stats will not be affected)
    cache.stats.pause()

    # Resume tracking
    cache.stats.resume()

    # Reset stats
    cache.stats.reset()

    # Disable stats (WARNING: This resets stats)
    cache.stats.disable()

    # Disable via configure() (WARNING: This resets stats)
    cache.configure(enable_stats=False)


Manage multiple caches using ``CacheManager``:

.. code-block:: python

    from cacheout import CacheManager

    cacheman = CacheManager({'a': {'maxsize': 100},
                             'b': {'maxsize': 200, 'ttl': 900},
                             'c': {})

    cacheman['a'].set('key1', 'value1')
    value = cacheman['a'].get('key')

    cacheman['b'].set('key2', 'value2')
    assert cacheman['b'].maxsize == 200
    assert cacheman['b'].ttl == 900

    cacheman['c'].set('key3', 'value3')

    cacheman.clear_all()
    for name, cache in cacheman:
        assert name in cacheman
        assert len(cache) == 0


For more details, see the full documentation at https://cacheout.readthedocs.io.



.. |version| image:: https://img.shields.io/pypi/v/cacheout.svg?style=flat-square
    :target: https://pypi.python.org/pypi/cacheout/

.. |build| image:: https://img.shields.io/github/actions/workflow/status/dgilland/cacheout/main.yml?branch=master&style=flat-square
    :target: https://github.com/dgilland/cacheout/actions

.. |coveralls| image:: https://img.shields.io/coveralls/dgilland/cacheout/master.svg?style=flat-square
    :target: https://coveralls.io/r/dgilland/cacheout

.. |license| image:: https://img.shields.io/pypi/l/cacheout.svg?style=flat-square
    :target: https://pypi.python.org/pypi/cacheout/
