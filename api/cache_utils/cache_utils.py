from django.core.cache import cache

def cache_func(callable, key, seconds):
    if res1 := cache.get(key):
        return res1
    res2 = callable()
    cache.set(key, res2, seconds)
    return res2
