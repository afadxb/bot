# sentiment/utils/cache.py

import functools
import time

_cache_store = {}

def cache_result(ttl_minutes=5):
    def decorator_cache(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (func.__name__, args, tuple(kwargs.items()))
            if key in _cache_store:
                cached_time, result = _cache_store[key]
                if time.time() - cached_time < ttl_minutes * 60:
                    return result
            result = func(*args, **kwargs)
            _cache_store[key] = (time.time(), result)
            return result
        return wrapper
    return decorator_cache
