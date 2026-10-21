"""限速与指数退避重试(SPEC §4.3)。

默认:每 2 秒 1 请求 + 0.5~1.5s 随机抖动;重试最多 3 次,退避基数 2s。
`RiskControlError` 绝不重试。
"""

from __future__ import annotations

import random
import time
from typing import Callable, Iterable, TypeVar

from .exceptions import RiskControlError

T = TypeVar("T")


class RateLimiter:
    def __init__(
        self,
        interval: float = 2.0,
        jitter: tuple[float, float] = (0.5, 1.5),
        *,
        sleep: Callable[[float], None] = time.sleep,
        rand: Callable[[float, float], float] = random.uniform,
    ):
        self.interval = interval
        self.jitter = jitter
        self._sleep = sleep
        self._rand = rand
        self._last: float | None = None

    def wait(self) -> None:
        now = time.monotonic()
        if self._last is not None:
            remain = self.interval - (now - self._last)
            if remain > 0:
                self._sleep(remain)
        self._sleep(self._rand(*self.jitter))
        self._last = time.monotonic()


def with_retry(
    func: Callable[[], T],
    *,
    max_retries: int = 3,
    base_delay: float = 2.0,
    retryable: Iterable[type[BaseException]] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
    on_retry: Callable[[int, BaseException], None] | None = None,
) -> T:
    """指数退避重试。`RiskControlError` 立即向上抛,绝不重试。"""
    retryable_t = tuple(retryable)
    attempt = 0
    while True:
        try:
            return func()
        except RiskControlError:
            raise
        except retryable_t as exc:  # noqa: PERF203
            attempt += 1
            if attempt > max_retries:
                raise
            if on_retry:
                on_retry(attempt, exc)
            sleep(base_delay * (2 ** (attempt - 1)))
