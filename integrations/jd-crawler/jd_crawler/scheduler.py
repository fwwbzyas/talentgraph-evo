"""定时循环调度(SPEC §4.15):按固定间隔重复执行批量抓取,支撑时间维度上的持续采集。

- 进程内调度:每 `interval_hours` 跑一轮 `run_once()`(通常是 BatchRunner.run);
  需要系统级调度时可改用 Windows 任务计划 / cron 直接调用 CLI(见 README)。
- 轮次历史持久化到 scheduler_state.json(run_id、新增条数、失败组合数、
  风控停站列表),供后续巡检。
- KeyboardInterrupt 优雅退出:状态先落盘再退出。
- 风控停站的站点在下一轮仍会重试(间隔通常足够长,且每轮 fresh_pages);
  若平台持续风控,请直接停止使用该站点。
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("jd_crawler.scheduler")


class Scheduler:
    def __init__(
        self,
        run_once: Callable[[], object],
        *,
        interval_hours: float = 24.0,
        max_runs: Optional[int] = None,
        state_path: str | Path | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.run_once = run_once
        self.interval_hours = max(interval_hours, 0.05)  # 下限约 3 分钟,防误配
        self.max_runs = max_runs
        self.state_path = Path(state_path) if state_path else None
        self.sleep = sleep

    def _record(self, entry: dict) -> None:
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        history: list[dict] = []
        if self.state_path.exists():
            history = json.loads(self.state_path.read_text(encoding="utf-8"))
        history.append(entry)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        tmp.replace(self.state_path)

    def run(self) -> int:
        """返回已完成的轮数。"""
        n = 0
        try:
            while True:
                started = datetime.now(timezone.utc)
                logger.info("===== 第 %d 轮开始 %s =====", n + 1,
                            started.astimezone().strftime("%Y-%m-%d %H:%M:%S"))
                entry: dict = {"started_at": started.isoformat()}
                try:
                    summary = self.run_once()
                    if hasattr(summary, "to_dict"):
                        d = summary.to_dict()
                        entry.update({
                            "run_id": d.get("run_id"),
                            "new_jobs": d.get("new_jobs"),
                            "failed_combos": d.get("failed_combos"),
                            "risk_stopped_sites": d.get("risk_stopped_sites"),
                        })
                    entry["status"] = "ok"
                except Exception:
                    entry["status"] = "error"
                    logger.exception("第 %d 轮执行异常", n + 1)
                entry["finished_at"] = datetime.now(timezone.utc).isoformat()
                self._record(entry)
                n += 1
                if self.max_runs is not None and n >= self.max_runs:
                    logger.info("已达最大轮数 %d,调度结束。", self.max_runs)
                    return n
                nxt = datetime.now(timezone.utc) + timedelta(hours=self.interval_hours)
                logger.info(
                    "第 %d 轮结束;下一轮约 %s(间隔 %.1f 小时)。Ctrl+C 可停止。",
                    n, nxt.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                    self.interval_hours,
                )
                # 分片 sleep:保证长时间等待中 Ctrl+C 也能较快响应
                remaining = self.interval_hours * 3600
                while remaining > 0:
                    step = min(30.0, remaining)
                    self.sleep(step)
                    remaining -= step
        except KeyboardInterrupt:
            logger.info("收到中断信号,调度器退出(已完成 %d 轮,状态已保存)。", n)
            return n
