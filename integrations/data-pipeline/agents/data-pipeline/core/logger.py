"""
结构化日志模块

对应 多Agent协作开发规范 4.4:
  - 结构化日志（JSON 行）
  - 每条日志带 trace_id 和 agent
  - 日志级别: DEBUG/INFO/WARNING/ERROR
"""

import sys
import logging
from datetime import datetime, timezone
from typing import Optional


class JsonLogger:
    """
    轻量级结构化日志。

    输出每条日志为一行 JSON，包含 timestamp / level / agent / trace_id / message / extras。
    比 print() 可解析，比 structlog 零依赖。
    """

    def __init__(self, name: str = "pipeline", agent: str = "data-pipeline"):
        self.name = name
        self.agent = agent
        self._trace_id: Optional[str] = None

    def set_trace_id(self, trace_id: str):
        self._trace_id = trace_id

    def _emit(self, level: str, message: str, **extras):
        import json
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "agent": self.agent,
            "trace_id": self._trace_id or "-",
            "message": message,
            **extras,
        }
        print(json.dumps(record, ensure_ascii=False), file=sys.stderr)

    def debug(self, msg, **kw):
        self._emit("DEBUG", msg, **kw)

    def info(self, msg, **kw):
        self._emit("INFO", msg, **kw)

    def warning(self, msg, **kw):
        self._emit("WARNING", msg, **kw)

    def error(self, msg, **kw):
        self._emit("ERROR", msg, **kw)

    # 兼容 print 调用风格的便捷方法
    def section(self, title: str):
        """打印分隔段标题（终端友好）。"""
        print(f"\n{'='*60}\n  {title}\n{'='*60}")

    def step(self, step_name: str, status: str = "", **kw):
        """打印采集步骤进度。"""
        if status:
            print(f"  [{step_name}] {status}")
        self.info(f"{step_name}: {status}", **kw)


# 全局默认实例
_default_logger: Optional[JsonLogger] = None


def get_logger() -> JsonLogger:
    global _default_logger
    if _default_logger is None:
        _default_logger = JsonLogger()
    return _default_logger


def setup_logging(agent_name: str = "data-pipeline", trace_id: Optional[str] = None):
    global _default_logger
    _default_logger = JsonLogger(agent=agent_name)
    if trace_id:
        _default_logger.set_trace_id(trace_id)
    return _default_logger
