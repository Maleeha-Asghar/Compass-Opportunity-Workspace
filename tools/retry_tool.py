import time
from collections.abc import Callable
from typing import TypeVar

import requests

T = TypeVar("T")


def with_backoff(
    operation: Callable[[], T],
    *,
    retries: int = 4,
    base_delay: float = 1.0,
    retry_exceptions: tuple[type[BaseException], ...] = (requests.RequestException,),
) -> T:
    for attempt in range(retries + 1):
        try:
            return operation()
        except retry_exceptions:
            if attempt == retries:
                raise
            time.sleep(min(base_delay * (2**attempt), 30.0))
    raise RuntimeError("unreachable retry state")
