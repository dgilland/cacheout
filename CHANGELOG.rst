Changelog
=========


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
