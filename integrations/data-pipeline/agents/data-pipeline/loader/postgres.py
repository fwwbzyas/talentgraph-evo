"""
数据入库模块 — PostgreSQL 加载器

将清洗后的数据写入 PostgreSQL，支持:
  - 原始数据入库 (raw_job_descriptions)
  - 清洗数据入库 (cleaned_job_descriptions)
  - JSON 降级模式（数据库不可用时）
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from contracts.data_schema import RawJobDescription, CleanedJobDescription, QualityReport


class DataLoader:
    """
    数据加载器

    PostgreSQL 模式:
      - 需要 psycopg2（可选依赖）
      - 连接: postgresql://app:dev_only_pwd@localhost:5432/job_kg

    JSON 降级模式（默认）:
      - 写入 ./output/ 目录
      - 不依赖数据库，开箱即用
    """

    def __init__(self, dsn: Optional[str] = None, output_dir: str = "./output"):
        self.dsn = dsn or "postgresql://app:dev_only_pwd@localhost:5432/job_kg"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._use_db = self._check_db()

    def _check_db(self) -> bool:
        """检测数据库是否可用"""
        try:
            import psycopg2
            conn = psycopg2.connect(self.dsn)
            conn.close()
            print("[Loader] PostgreSQL 连接成功")
            return True
        except Exception:
            print("[Loader] PostgreSQL 不可用，将使用 JSON 文件模式")
            return False

    # ── 原始数据 ─────────────────────────

    def save_raw(self, jds: list[RawJobDescription]) -> int:
        """保存原始 JD 数据"""
        if self._use_db:
            return self._save_raw_db(jds)
        else:
            return self._save_raw_json(jds)

    def _save_raw_json(self, jds: list[RawJobDescription]) -> int:
        """JSON 文件模式 — 保存原始数据"""
        raw_dir = self.output_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = raw_dir / f"raw_jds_{timestamp}.json"

        data = [jd.model_dump(mode="json") for jd in jds]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        print(f"[Loader] 原始数据已保存: {filepath} ({len(jds)} 条)")
        return len(jds)

    def _save_raw_db(self, jds: list[RawJobDescription]) -> int:
        """PostgreSQL 模式 — 保存原始数据"""
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(self.dsn)
        count = 0
        try:
            with conn.cursor() as cur:
                for jd in jds:
                    raw_id = hashlib.md5(jd.source_url.encode()).hexdigest()[:12]
                    cur.execute(
                        """INSERT INTO raw_job_descriptions
                           (id, source, source_url, title, company, description,
                            required_skills_raw, optional_skills_raw,
                            salary_range, location, experience, education,
                            publish_date, crawl_timestamp)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (id) DO NOTHING""",
                        (
                            raw_id, jd.source.value, jd.source_url,
                            jd.title, jd.company, jd.description,
                            jd.required_skills_raw, jd.optional_skills_raw,
                            jd.salary_range, jd.location,
                            jd.experience, jd.education,
                            jd.publish_date, jd.crawl_timestamp,
                        ),
                    )
                    count += cur.rowcount
            conn.commit()
        finally:
            conn.close()
        print(f"[Loader] 原始数据已写入 PostgreSQL ({count} 条新增)")
        return count

    # ── 清洗数据 ─────────────────────────

    def save_cleaned(self, jds: list[CleanedJobDescription]) -> int:
        """保存清洗后的 JD 数据"""
        if self._use_db:
            return self._save_cleaned_db(jds)
        else:
            return self._save_cleaned_json(jds)

    def _save_cleaned_json(self, jds: list[CleanedJobDescription]) -> int:
        """JSON 文件模式 — 保存清洗数据"""
        clean_dir = self.output_dir / "cleaned"
        clean_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = clean_dir / f"cleaned_jds_{timestamp}.json"

        data = [jd.model_dump(mode="json") for jd in jds]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        print(f"[Loader] 清洗数据已保存: {filepath} ({len(jds)} 条)")
        return len(jds)

    def _save_cleaned_db(self, jds: list[CleanedJobDescription]) -> int:
        """PostgreSQL 模式 — 保存清洗数据"""
        import psycopg2

        conn = psycopg2.connect(self.dsn)
        count = 0
        try:
            with conn.cursor() as cur:
                for jd in jds:
                    clean_id = hashlib.md5(
                        f"{jd.raw_id}_cleaned".encode()
                    ).hexdigest()[:12]
                    cur.execute(
                        """INSERT INTO cleaned_job_descriptions
                           (id, raw_id, source, title, company, description_clean,
                            skills, quality_score, quality_level,
                            is_duplicate, is_plagiarized, is_ai_generated,
                            freshness_weight, cleaning_trace, cleaned_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (id) DO UPDATE SET
                            quality_score = EXCLUDED.quality_score,
                            quality_level = EXCLUDED.quality_level,
                            cleaning_trace = EXCLUDED.cleaning_trace""",
                        (
                            clean_id, jd.raw_id, jd.source.value,
                            jd.title, jd.company, jd.description_clean,
                            json.dumps(
                                [s.model_dump() for s in jd.skills],
                                ensure_ascii=False,
                            ),
                            jd.quality_score, jd.quality_level.value,
                            jd.is_duplicate, jd.is_plagiarized,
                            jd.is_ai_generated,
                            jd.freshness_weight,
                            json.dumps(
                                jd.cleaning_trace.model_dump(),
                                ensure_ascii=False,
                            ),
                            jd.cleaned_at,
                        ),
                    )
                    count += cur.rowcount
            conn.commit()
        finally:
            conn.close()
        print(f"[Loader] 清洗数据已写入 PostgreSQL ({count} 条)")
        return count

    # ── 质量报告 ─────────────────────────

    def save_report(self, report: QualityReport):
        """保存质量报告"""
        report_dir = self.output_dir / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = report_dir / f"quality_report_{timestamp}.json"

        data = report.model_dump(mode="json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        print(f"[Loader] 质量报告已保存: {filepath}")
