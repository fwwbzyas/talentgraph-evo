"""Scheduler:固定轮数、状态持久化、异常容错、优雅中断。"""

import json

from jd_crawler.batch import ComboResult, RunSummary
from jd_crawler.scheduler import Scheduler


def _summary(run_id="r1", new_jobs=5):
    return RunSummary(run_id=run_id, started_at="2026-08-13T00:00:00+00:00",
                      combos=[ComboResult("51job", "北京", "算法工程师",
                                          new_jobs=new_jobs)])


def test_scheduler_runs_max_runs_and_persists_state(tmp_path):
    calls = {"n": 0}

    def run_once():
        calls["n"] += 1
        return _summary(run_id=f"r{calls['n']}")

    state = tmp_path / "scheduler_state.json"
    sch = Scheduler(run_once, interval_hours=0.05, max_runs=3,
                    state_path=state, sleep=lambda s: None)
    assert sch.run() == 3
    history = json.loads(state.read_text(encoding="utf-8"))
    assert len(history) == 3
    assert history[0]["run_id"] == "r1"
    assert history[0]["new_jobs"] == 5
    assert history[0]["status"] == "ok"


def test_scheduler_survives_run_exception(tmp_path):
    calls = {"n": 0}

    def run_once():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return _summary()

    state = tmp_path / "s.json"
    sch = Scheduler(run_once, interval_hours=1, max_runs=2,
                    state_path=state, sleep=lambda s: None)
    assert sch.run() == 2
    history = json.loads(state.read_text(encoding="utf-8"))
    assert history[0]["status"] == "error"
    assert history[1]["status"] == "ok"


def test_scheduler_keyboard_interrupt_exits_gracefully(tmp_path):
    state = tmp_path / "s.json"

    def interrupting_sleep(_):
        raise KeyboardInterrupt

    sch = Scheduler(lambda: _summary(), interval_hours=1, max_runs=None,
                    state_path=state, sleep=interrupting_sleep)
    assert sch.run() == 1  # 完成一轮后等待期被中断
    assert len(json.loads(state.read_text(encoding="utf-8"))) == 1
