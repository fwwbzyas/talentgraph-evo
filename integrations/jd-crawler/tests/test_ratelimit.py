import pytest

from jd_crawler.exceptions import FetchError, RiskControlError
from jd_crawler.ratelimit import RateLimiter, with_retry


class FakeClock:
    def __init__(self):
        self.slept: list[float] = []

    def sleep(self, s: float) -> None:
        self.slept.append(s)


def test_rate_limiter_interval_and_jitter():
    clock = FakeClock()
    rl = RateLimiter(interval=2.0, jitter=(0.5, 1.5), sleep=clock.sleep,
                     rand=lambda a, b: 1.0)  # 固定抖动便于断言
    rl.wait()
    rl.wait()
    # 第一次:只有抖动;第二次:间隔(接近2s,因无真实流逝)+ 抖动
    assert clock.slept[0] == 1.0
    assert 1.9 <= clock.slept[1] <= 3.1  # interval(≈2) + jitter(1.0)


def test_with_retry_eventually_succeeds():
    clock = FakeClock()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise FetchError("boom")
        return "ok"

    assert with_retry(flaky, max_retries=3, base_delay=2.0,
                      retryable=(FetchError,), sleep=clock.sleep) == "ok"
    assert calls["n"] == 3
    assert clock.slept == [2.0, 4.0]  # 指数退避


def test_with_retry_gives_up_after_max():
    def always_fail():
        raise FetchError("boom")

    with pytest.raises(FetchError):
        with_retry(always_fail, max_retries=3, base_delay=0.01,
                   retryable=(FetchError,), sleep=lambda s: None)


def test_risk_control_never_retried():
    calls = {"n": 0}

    def risky():
        calls["n"] += 1
        raise RiskControlError("51job", "http://x", "waf")

    with pytest.raises(RiskControlError):
        with_retry(risky, max_retries=3, retryable=(Exception,), sleep=lambda s: None)
    assert calls["n"] == 1  # 绝不重试
