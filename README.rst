cacheout
********

|version| |travis| |coveralls| |license|


A caching library for Python.


Links
=====

- Project: https://github.com/dgilland/cacheout
- Documentation: https://cacheout.readthedocs.io
- PyPI: https://pypi.python.org/pypi/cacheout/
- TravisCI: https://travis-ci.org/dgilland/cacheout


Features
========

- In-memory caching using dictionary backend
- Cache manager for easily accessing multiple cache objects
- Reconfigurable cache settings for runtime setup when using module-level cache objects
- Maximum cache size enforcement
- Default cache TTL (time-to-live) as well as custom TTLs per cache entry
- Bulk set, get, and delete operations
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

- Memoization decorator
- Layered caching (multi-level caching)
- Cache event listener support (e.g. on-get, on-set, on-delete)
- Regular expression support in cache get
- Set-on-missing callback support in cache get
- Cache statistics (e.g. cache hits/misses, cache frequency, etc)


Requirements
============

- Python >= 3.4


Quickstart
==========

Install using pip:


::

    pip install cacheout


Let's start with some basic caching by creating a cache object:

.. code-block:: python

    from cacheout import Cache

    cache = Cache()


By default the ``cache`` object will have a maximum size of ``300`` and default TTL expiration turned off. These values can be set with:

.. code-block:: python

    cache = Cache(maxsize=300, ttl=0, timer=time.time)  # defaults


Set a cache key using ``cache.set()``:

.. code-block:: python

    cache.set(1, 'foobar')


Get the value of a cache key with ``cache.get()``:

.. code-block:: python

    assert cache.get(1) == 'foobar'


Set the TTL (time-to-live) expiration per entry:

.. code-block:: python

    cache.set(3, {'data': {}}, ttl=1)
    assert cache.get(3) == {'data': {}}
    time.sleep(1)
    assert cache.get(3) is None


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

.. |travis| image:: https://img.shields.io/travis/dgilland/cacheout/master.svg?style=flat-square
    :target: https://travis-ci.org/dgilland/cacheout

.. |coveralls| image:: https://img.shields.io/coveralls/dgilland/cacheout/master.svg?style=flat-square
    :target: https://coveralls.io/r/dgilland/cacheout

.. |license| image:: https://img.shields.io/pypi/l/cacheout.svg?style=flat-square
    :target: https://pypi.python.org/pypi/cacheout/
