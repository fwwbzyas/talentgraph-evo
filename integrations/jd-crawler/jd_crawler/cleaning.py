"""数据清洗层(SPEC §4.14):为下游清洗算法预留的扩展空间。

设计:
- `Cleaner` 协议:任何实现 `clean(record: dict) -> dict | None` 的对象都可
  挂入清洗链;返回 None 表示丢弃该记录。
- `CleaningPipeline` 按序执行清洗器,读取 output/raw/ 的 JSONL,
  写出**缩进格式化 JSON** 到 output/cleaned/(与 raw 一一对应,另附汇总)。
- 内置清洗器均为**非破坏性**的(规范化而非改写语义):
  - `WhitespaceCleaner`:压缩各文本字段多余空白;
  - `SalaryNormCleaner`:派生 `salary_norm` 字段(统一为 "X-Yk/月" 估算,
    原 `salary` 字段不动);
  - `CrossSourceDedupCleaner`:跨站点按 (标准化标题, 标准化公司, 城市) 去重,
    标记 `dup_of` 而不删除(默认保留全部记录,仅打标)。

后续可在此处挂接:薪资区间解析、公司名归一化(去后缀)、职位类别分类器、
JD 正文分词/技能词抽取、embedding 去重等更重的算法。

CLI:`python -m jd_crawler.cli --clean`(或交互菜单第 4 项)。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional, Protocol

logger = logging.getLogger("jd_crawler.cleaning")


class Cleaner(Protocol):
    name: str

    def clean(self, record: dict) -> Optional[dict]:
        """返回清洗后的记录;返回 None 表示丢弃。"""
        ...


class WhitespaceCleaner:
    name = "whitespace"

    _FIELDS = ("title", "salary", "city", "company_name", "experience",
               "education", "publish_date", "description", "keyword",
               "search_city")

    def clean(self, record: dict) -> Optional[dict]:
        for f in self._FIELDS:
            v = record.get(f)
            if isinstance(v, str):
                record[f] = re.sub(r"\s+", " ", v).strip()
        return record


_SALARY_RE = re.compile(
    r"(?P<lo>\d+(?:\.\d+)?)\s*[-~]\s*(?P<hi>\d+(?:\.\d+)?)\s*(?P<unit>万|千|k|K)"
)


class SalaryNormCleaner:
    """派生 salary_norm("X-Yk/月" 估算),不改原字段。无法解析时为空串。"""

    name = "salary_norm"

    def clean(self, record: dict) -> Optional[dict]:
        raw = record.get("salary") or ""
        record["salary_norm"] = self._norm(raw)
        return record

    @staticmethod
    def _norm(raw: str) -> str:
        m = _SALARY_RE.search(raw)
        if not m:
            return ""
        lo, hi = float(m.group("lo")), float(m.group("hi"))
        unit = m.group("unit")
        if unit == "万":
            lo, hi = lo * 10, hi * 10
        elif unit == "千":
            lo, hi = lo, hi  # 千 == k
        # 年薪(含"/年"或"薪"超过12按月薪折算的特例不处理,只做月口径)
        if "/年" in raw:
            lo, hi = lo / 12, hi / 12
        return f"{lo:g}-{hi:g}k/月"


def _norm_company(name: str) -> str:
    name = re.sub(r"\s+", "", name or "").lower()
    return re.sub(
        r"(有限责任公司|股份有限公司|有限公司|集团|公司)$", "", name,
    )


class CrossSourceDedupCleaner:
    """跨站点软去重:相同 (标题, 公司, 城市) 的后到记录打 dup_of 标,不删除。"""

    name = "cross_source_dedup"

    def __init__(self):
        self._seen: dict[tuple[str, str, str], str] = {}

    def clean(self, record: dict) -> Optional[dict]:
        key = (
            re.sub(r"\s+", "", record.get("title") or "").lower(),
            _norm_company(record.get("company_name") or ""),
            (record.get("search_city") or record.get("city") or "").strip(),
        )
        if all(key):
            first = self._seen.get(key)
            if first is not None:
                record["dup_of"] = first
            else:
                self._seen[key] = record.get("dedup_key") or ""
        return record


def default_cleaners() -> list[Cleaner]:
    return [WhitespaceCleaner(), SalaryNormCleaner(), CrossSourceDedupCleaner()]


class CleaningPipeline:
    def __init__(self, cleaners: list[Cleaner] | None = None):
        self.cleaners = cleaners if cleaners is not None else default_cleaners()

    def apply(self, record: dict) -> Optional[dict]:
        for c in self.cleaners:
            record = c.clean(record)
            if record is None:
                return None
        return record

    def clean_file(self, src: str | Path, dst: str | Path) -> tuple[int, int]:
        """清洗单个 JSONL → 格式化 JSON。返回 (读入条数, 写出条数)。"""
        src, dst = Path(src), Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        kept: list[dict] = []
        total = 0
        with open(src, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                total += 1
                rec = self.apply(json.loads(line))
                if rec is not None:
                    kept.append(rec)
        dst.write_text(
            json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        return total, len(kept)


def run_cleaning(
    raw_dir: str | Path,
    cleaned_dir: str | Path,
    cleaners: list[Cleaner] | None = None,
) -> dict[str, dict[str, int]]:
    """清洗 raw_dir 下全部 *.jsonl,结果写入 cleaned_dir。返回每文件统计。"""
    raw_dir, cleaned_dir = Path(raw_dir), Path(cleaned_dir)
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, dict[str, int]] = {}
    files = sorted(raw_dir.glob("*.jsonl"))
    if not files:
        logger.warning("未发现待清洗文件: %s/*.jsonl", raw_dir)
        return report
    # 跨文件共享同一条清洗链(跨站点软去重才能生效)
    pipeline = CleaningPipeline(cleaners)
    for f in files:
        out = cleaned_dir / f"{f.stem}.cleaned.json"
        total, kept = pipeline.clean_file(f, out)
        report[f.name] = {"in": total, "out": kept, "path": str(out)}
        logger.info("清洗 %s: %d -> %d (%s)", f.name, total, kept, out)
    (cleaned_dir / "clean_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return report
