Changelog
=========


v0.16.0 (2023-12-22)
--------------------

- Add ``Cache.on_get`` callback hook. Thanks uncle-lv_!
- Add ``Cache.on_set`` callback hook. Thanks uncle-lv_!


v0.15.0 (2023-11-03)
--------------------

- Add cache statistics. Thanks uncle-lv_!
- Add ``Cache.get_ttl``. Thanks uncle-lv_!
- Add ``Cache.on_delete`` callback hook. Thanks uncle-lv_!
- Add support for Python 3.11 and 3.12.


v0.14.1 (2022-08-16)
--------------------

- Set minimum Python version to 3.7 in setup.cfg.


v0.14.0 (2022-08-16)
--------------------

- Add support for Python 3.10.
- Drop support for Python 3.6. Minimum supported version is 3.7.
- Clarify docs around TTL to make it explicit what time units it uses by default.


v0.13.1 (2021-04-28)
--------------------

- Minor optimization in ``Cache.get_many|delete_many``.


v0.13.0 (2021-04-27)
--------------------

- Add ``cache_key`` attribute to memoized functions that can be used to generate the cache key used for a given set of function arguments. Thanks johnbergvall_!
- Fix bug in ``Cache.full`` that would result in an exception if cache created with ``maxsize=None`` like ``Cache(maxsize=None)``. Thanks AllinolCP_!
- Fix bug in ``Cache.get_many`` that resulted in ``RuntimeError: OrderedDict mutated during iteration`` when cache keys expire during the ``get_many`` call.
- Remove ``default`` argument from ``Cache.get_many``. A default value on missing cache key was only ever returned if a list of keys was passed in and those keys happened to expire during the ``get_many`` call. **breaking change**


v0.12.1 (2021-04-19)
--------------------

- Fix regression in ``0.12.0`` that resulted in missing docstrings for some methods of ``LFUCache`` and ``LRUCache``.


v0.12.0 (2021-04-19)
--------------------

- Fix bug in ``Cache.__contains__`` where it would return ``True`` for an expired key.
- Add type annotations.
- Add official support for Python 3.8 and 3.9.
- Drop support for Python 3.4 and 3.5.


v0.11.2 (2019-09-30)
--------------------

- Fix bug in ``LFUCache`` that would result cache growing beyond ``maxsize`` limit.


v0.11.1 (2019-01-09)
--------------------

- Fix issue with asyncio support in memoization decorators that caused a ``RuntimeError: await wasn't used with future`` when certain types of async functions were used inside the memoized function.


v0.11.0 (2018-10-19)
--------------------

- Add asyncio support to memoization decorators so they can decorate coroutines.


v0.10.3 (2018-08-01)
--------------------

- Expose ``typed`` argument of underlying ``*Cache.memoize()`` in ``memoize()`` and ``*_memoize()`` decorators.


v0.10.2 (2018-07-31)
--------------------

- Fix bug in ``LRUCache.get()`` where supplying a ``default`` value would result in a ``KeyError``.


v0.10.1 (2018-07-15)
--------------------

- Support Python 3.7.


v0.10.0 (2018-04-03)
--------------------

- Modify behavior of ``default`` argument to ``Cache.get()`` so that if ``default`` is a callable and the cache key is missing, then it will be called and its return value will be used as the value for cache key and subsequently be set as the value for the key in the cache. (**breaking change**)
- Add ``default`` argument to ``Cache()`` that can be used to override the value for ``default`` in ``Cache.get()``.


v0.9.0 (2018-03-31)
-------------------

- Merge functionality of ``Cache.get_many_by()`` into ``Cache.get_many()`` and remove ``Cache.get_many_by()``. (**breaking change**).
- Merge functionality of ``Cache.delete_many_by()`` into ``Cache.delete_many()`` and remove ``Cache.delete_many_by()``. (**breaking change**).


v0.8.0 (2018-03-30)
-------------------

- Add ``Cache.get_many_by()``.
- Add ``Cache.delete_many_by()``.
- Make ``Cache.keys()`` and ``Cache.values()`` return dictionary view objects instead of yielding items. (**breaking change**)


v0.7.0 (2018-02-22)
-------------------

- Changed default cache ``maxsize`` from ``300`` to ``256``. (**breaking change**)
- Add ``Cache.memoize()`` decorator.
- Add standalone memoization decorators:

  - ``memoize``
  - ``fifo_memoize``
  - ``lfu_memoize``
  - ``lifo_memoize``
  - ``lru_memoize``
  - ``mru_memoize``
  - ``rr_memoize``


v0.6.0 (2018-02-05)
-------------------

- Add ``LIFOCache``
- Add ``FIFOCache`` as an alias of ``Cache``.


v0.5.0 (2018-02-04)
-------------------

- Add ``LFUCache``
- Delete expired items before popping an item in ``Cache.popitem()``.


v0.4.0 (2018-02-02)
-------------------

- Add ``MRUCache``
- Add ``RRCache``
- Add ``Cache.popitem()``.
- Rename ``Cache.expirations()`` to ``Cache.expire_times()``. (**breaking change**)
- Rename ``Cache.count()`` to ``Cache.size()``. (**breaking change**)
- Remove ``minimum`` arguement from ``Cache.evict()``. (**breaking change**)


v0.3.0 (2018-01-31)
-------------------

- Add ``LRUCache``.
- Add ``CacheManager.__repr__()``.
- Make threading lock usage in ``Cache`` more fine-grained and eliminate redundant locking.
- Fix missing thread-safety in ``Cache.__len__()`` and ``Cache.__contains__()``.


v0.2.0 (2018-01-30)
-------------------

- Rename ``Cache.setup()`` to ``Cache.configure()``. (**breaking change**)
- Add ``CacheManager`` class.


v0.1.0 (2018-01-28)
-------------------

- Add ``Cache`` class.


.. _johnbergvall: https://github.com/johnbergvall
.. _AllinolCP: https://github.com/AllinolCP
.. _uncle-lv: https://github.com/uncle-lv
