# sentiment/utils/retry.py

import time
import functools

def retry(times=3, backoff=5):
    def decorator_retry(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == times - 1:
                        raise
                    time.sleep(backoff * (2 ** attempt))
        return wrapper
    return decorator_retry
