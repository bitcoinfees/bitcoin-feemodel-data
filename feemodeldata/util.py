import pytz
from calendar import timegm
from time import sleep
from functools import wraps


def utc_to_timestamp(dt):
    """Convert utc datetime to unix timestamp."""
    dt_utc = pytz.utc.localize(dt)
    return timegm(dt_utc.utctimetuple())


def retry(wait=1, maxtimes=3, logger=None):
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
                    if logger:
                        logger.exception(
                            "{} in {}, trying again in {}s, "
                            "{} of {} tries left.".
                            format(e.__class__.__name__, fn.__name__,
                                   wait, maxtimes-numtries, maxtimes))
                    if numtries == maxtimes:
                        raise e
                    sleep(wait)
        return decorated
    return decorator
