Changelog
=========


v0.3.0 (2018-01-31)
-------------------

- Add ``LRUCache``.
- Add ``CacheManager.__repr__()``.
- Make threading lock usage in ``Cache`` more fine-grained and eliminate redundant locking.
- Fix missing thread-safety in ``Cache.__len__()`` and ``Cache.__contains__()``.


v0.2.0 (2018-01-30)
-------------------

- Rename ``Cache.setup()`` to ``Cache.configure()``. **breaking change**
- Add ``CacheManager`` class.


v0.1.0 (2018-01-28)
-------------------

- Add ``Cache`` class.
