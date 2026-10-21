"""统一职位 JD 数据模型(SPEC §3)。

注意:模型中**不存在**任何求职者/HR 个人信息字段,从结构上保证
"只采集公开免登录 JD 字段"的硬约束。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .sanitize import mask_contacts

Source = Literal["51job", "liepin"]


class JobPosting(BaseModel):
    source: Source
    job_id: str
    title: str
    salary: Optional[str] = None
    city: Optional[str] = None
    company_name: Optional[str] = None
    experience: Optional[str] = None
    education: Optional[str] = None
    publish_date: Optional[str] = None
    description: str = ""
    job_url: str
    company_tags: list[str] = Field(default_factory=list)
    # 检索上下文(由 spider 在产出时标注;便于矩阵批量入库后的统计追溯)
    keyword: Optional[str] = None
    search_city: Optional[str] = None
    crawled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context) -> None:  # noqa: D401
        # 入库前强制脱敏(防御性:解析器拿到的任何文本都过一遍)
        self.title = mask_contacts(self.title).strip()
        self.description = mask_contacts(self.description).strip()
        for f in ("salary", "city", "company_name", "experience", "education", "publish_date"):
            v = getattr(self, f)
            if v:
                setattr(self, f, mask_contacts(v).strip())

    @property
    def dedup_key(self) -> str:
        return f"{self.source}:{self.job_id}"
