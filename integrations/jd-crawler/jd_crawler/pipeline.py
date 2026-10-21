"""持久化与断点续爬(SPEC §4.9):JSONL + SQLite 双写、去重、checkpoint。"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from .models import JobPosting


class JsonlWriter:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a", encoding="utf-8")

    def write(self, job: JobPosting) -> None:
        self._fh.write(
            json.dumps(job.model_dump(mode="json"), ensure_ascii=False) + "\n"
        )
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


class SQLiteWriter:
    DDL = """
    CREATE TABLE IF NOT EXISTS jobs (
        dedup_key    TEXT PRIMARY KEY,
        source       TEXT NOT NULL,
        job_id       TEXT NOT NULL,
        title        TEXT,
        salary       TEXT,
        city         TEXT,
        company_name TEXT,
        experience   TEXT,
        education    TEXT,
        publish_date TEXT,
        description  TEXT,
        job_url      TEXT,
        keyword      TEXT,
        search_city  TEXT,
        crawled_at   TEXT,
        raw_json     TEXT
    );
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute(self.DDL)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """老库缺列时补列(轻量迁移,保证持续运行的历史库可复用)。"""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(jobs)")}
        for col in ("keyword", "search_city"):
            if col not in cols:
                self._conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT")

    def write(self, job: JobPosting) -> bool:
        cur = self._conn.execute(
            """INSERT OR IGNORE INTO jobs
               (dedup_key, source, job_id, title, salary, city, company_name,
                experience, education, publish_date, description, job_url,
                keyword, search_city, crawled_at, raw_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                job.dedup_key, job.source, job.job_id, job.title, job.salary,
                job.city, job.company_name, job.experience, job.education,
                job.publish_date, job.description, job.job_url,
                job.keyword, job.search_city,
                job.crawled_at.isoformat(),
                json.dumps(job.model_dump(mode="json"), ensure_ascii=False),
            ),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def stats(self) -> dict:
        """按站点/检索城市/关键词聚合的入库统计(供 CLI --stats)。"""
        cur = self._conn.execute(
            "SELECT COUNT(*), MIN(crawled_at), MAX(crawled_at) FROM jobs"
        )
        total, first, last = cur.fetchone()
        by_source = dict(
            self._conn.execute(
                "SELECT source, COUNT(*) FROM jobs GROUP BY source"
            ).fetchall()
        )
        by_city = self._conn.execute(
            "SELECT search_city, COUNT(*) FROM jobs "
            "WHERE search_city IS NOT NULL GROUP BY search_city ORDER BY 2 DESC"
        ).fetchall()
        by_keyword = self._conn.execute(
            "SELECT keyword, COUNT(*) FROM jobs "
            "WHERE keyword IS NOT NULL GROUP BY keyword ORDER BY 2 DESC"
        ).fetchall()
        return {
            "total": total or 0,
            "first_crawled": first,
            "last_crawled": last,
            "by_source": by_source,
            "by_search_city": by_city,
            "by_keyword": by_keyword,
        }

    def close(self) -> None:
        self._conn.close()


class DedupPipeline:
    """按 dedup_key(source:job_id)去重后双写 JSONL + SQLite。"""

    def __init__(self, jsonl: JsonlWriter, sqlite: SQLiteWriter):
        self.jsonl = jsonl
        self.sqlite = sqlite
        self._seen: set[str] = set()

    def process(self, job: JobPosting) -> bool:
        if job.dedup_key in self._seen:
            return False
        inserted = self.sqlite.write(job)
        if inserted:
            self.jsonl.write(job)
        self._seen.add(job.dedup_key)
        return inserted

    def close(self) -> None:
        self.jsonl.close()
        self.sqlite.close()


class Checkpoint:
    """断点续爬状态:已完成的列表页 + 已采职位 ID。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.done_pages: dict[str, list[int]] = {}
        self.done_jobs: set[str] = set()
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.done_pages = {k: list(v) for k, v in data.get("done_pages", {}).items()}
            self.done_jobs = set(data.get("done_jobs", []))

    @staticmethod
    def _site_key(site: str, keyword: str, city: str | None) -> str:
        return f"{site}|{keyword}|{city or ''}"

    def is_page_done(self, site: str, keyword: str, city: str | None, page: int) -> bool:
        return page in self.done_pages.get(self._site_key(site, keyword, city), [])

    def mark_page(self, site: str, keyword: str, city: str | None, page: int) -> None:
        key = self._site_key(site, keyword, city)
        pages = self.done_pages.setdefault(key, [])
        if page not in pages:
            pages.append(page)

    def is_job_done(self, job: JobPosting) -> bool:
        return job.dedup_key in self.done_jobs

    def mark_job(self, job: JobPosting) -> None:
        self.done_jobs.add(job.dedup_key)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "done_pages": self.done_pages,
                    "done_jobs": sorted(self.done_jobs),
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)  # 原子写
