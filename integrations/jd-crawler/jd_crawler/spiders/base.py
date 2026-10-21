"""Spider 基类(SPEC §4.6)。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from ..http import HttpClient
from ..models import JobPosting
from ..pipeline import Checkpoint


class BaseSpider(ABC):
    site: str = ""

    def __init__(self, http: HttpClient):
        self.http = http

    @abstractmethod
    def iter_jobs(
        self,
        keyword: str,
        city: str | None,
        max_pages: int,
        checkpoint: Checkpoint,
    ) -> Iterator[JobPosting]:
        """迭代产出职位。遇到 RiskControlError 直接向上抛(停站)。"""
