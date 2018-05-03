
def handle_change(instance, cache_class=None, **kwargs):
    cache = cache_class()
    cache.set(instance)


def handle_delete(instance, cache_class=None, **kwargs):
    cache = cache_class()
    cache.delete(instance)
