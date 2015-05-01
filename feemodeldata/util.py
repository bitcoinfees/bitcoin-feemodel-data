import logging
from time import sleep
from functools import wraps

logger = logging.getLogger(__name__)


def retry(wait=1, maxtimes=3):
    """Returns a retry decorator.

    Retries the decorated function until no exception is raised.
    wait specifies the time between retries in seconds.
    maxtimes specifies the max number of times to try (including the first).
    """
    def decorator(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            numtries = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    numtries += 1
                    logger.exception(
                        "{} in {}, trying again in {}s, {} of {} tries left.".
                        format(e.__class__.__name__, fn.__name__,
                               wait, maxtimes-numtries, maxtimes))
                    if numtries == maxtimes:
                        return None
                    sleep(wait)
        return decorated
    return decorator
