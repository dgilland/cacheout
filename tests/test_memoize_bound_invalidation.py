from cacheout import Cache


def test_bound_method_wrappers_can_invalidate_their_shared_entries():
    cache = Cache()

    class Service:
        def load(self, value):
            return value

    service, other = Service(), Service()
    first = cache.memoize()(service.load)
    second = cache.memoize()(service.load)
    unrelated = cache.memoize()(other.load)
    assert first(1) == 1
    assert second(2) == 2
    assert unrelated(3) == 3
    assert second.invalidate() == 2
    assert list(cache.values()) == [3]


def test_other_methods_on_the_same_instance_keep_their_entries():
    cache = Cache()

    class Service:
        def load(self, value):
            return value

        def save(self, value):
            return value

    service = Service()
    first = cache.memoize()(service.load)
    second = cache.memoize()(service.load)
    other = cache.memoize()(service.save)
    first(1)
    other(2)
    assert second.invalidate() == 1
    assert list(cache.values()) == [2]
