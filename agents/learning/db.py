from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .models import CourseDocument, JobProfile, LearningRoute


class CourseStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS job_profiles (
                    job_key TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    job_count INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS courses (
                    course_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    cover_url TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL,
                    instructor TEXT NOT NULL,
                    published_at TEXT,
                    duration_seconds INTEGER,
                    view_count INTEGER NOT NULL,
                    quality_score REAL NOT NULL,
                    difficulty TEXT NOT NULL,
                    language TEXT NOT NULL,
                    is_free INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS course_skills (
                    course_id TEXT NOT NULL,
                    skill TEXT NOT NULL,
                    relevance REAL NOT NULL,
                    PRIMARY KEY (course_id, skill),
                    FOREIGN KEY (course_id) REFERENCES courses(course_id)
                );
                CREATE INDEX IF NOT EXISTS idx_course_skills_skill ON course_skills(skill);
                CREATE TABLE IF NOT EXISTS learning_routes (
                    route_id TEXT PRIMARY KEY,
                    job_key TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS courses_fts USING fts5(
                    course_id UNINDEXED, title, summary, content, skills
                );
                CREATE TABLE IF NOT EXISTS course_link_health (
                    course_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    http_status INTEGER,
                    checked_at TEXT NOT NULL,
                    FOREIGN KEY (course_id) REFERENCES courses(course_id)
                );
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(courses)").fetchall()}
            if "cover_url" not in columns:
                connection.execute("ALTER TABLE courses ADD COLUMN cover_url TEXT NOT NULL DEFAULT ''")

    def replace_jobs(self, jobs: list[JobProfile]) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            for job in jobs:
                connection.execute(
                    "INSERT OR REPLACE INTO job_profiles VALUES (?, ?, ?, ?, ?, ?)",
                    (job.job_key, job.title, job.domain, job.job_count, job.model_dump_json(), now),
                )

    def list_jobs(self) -> list[JobProfile]:
        with self.connect() as connection:
            rows = connection.execute("SELECT payload FROM job_profiles ORDER BY job_count DESC, title").fetchall()
        return [JobProfile.model_validate_json(row["payload"]) for row in rows]

    def get_job(self, job_key: str) -> JobProfile | None:
        with self.connect() as connection:
            row = connection.execute("SELECT payload FROM job_profiles WHERE job_key = ?", (job_key,)).fetchone()
        return JobProfile.model_validate_json(row["payload"]) if row else None

    def upsert_course(self, course: CourseDocument) -> None:
        now = datetime.now(UTC).isoformat()
        content_hash = hashlib.sha256(course.content.encode("utf-8")).hexdigest()
        with self.connect() as connection:
            same_url = connection.execute(
                "SELECT course_id FROM courses WHERE url = ?", (course.url,),
            ).fetchone()
            if same_url and same_url[0] != course.course_id:
                old_id = same_url[0]
                old_skills = [row[0] for row in connection.execute(
                    "SELECT skill FROM course_skills WHERE course_id = ?", (old_id,),
                ).fetchall()]
                course.skills = list(dict.fromkeys([*old_skills, *course.skills]))
                connection.execute("DELETE FROM course_link_health WHERE course_id = ?", (old_id,))
                connection.execute("DELETE FROM course_skills WHERE course_id = ?", (old_id,))
                connection.execute("DELETE FROM courses_fts WHERE course_id = ?", (old_id,))
                connection.execute("DELETE FROM courses WHERE course_id = ?", (old_id,))
            connection.execute(
                """INSERT INTO courses (
                    course_id, source, title, url, cover_url, summary, instructor, published_at,
                    duration_seconds, view_count, quality_score, difficulty, language, is_free,
                    content, content_hash, raw_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(course_id) DO UPDATE SET
                    title=excluded.title,
                    cover_url=CASE WHEN excluded.cover_url != '' THEN excluded.cover_url ELSE courses.cover_url END,
                    summary=excluded.summary, instructor=excluded.instructor,
                    published_at=excluded.published_at, duration_seconds=excluded.duration_seconds,
                    view_count=excluded.view_count, quality_score=excluded.quality_score,
                    difficulty=excluded.difficulty, content=excluded.content,
                    content_hash=excluded.content_hash, raw_json=excluded.raw_json, updated_at=excluded.updated_at""",
                (
                    course.course_id, course.source, course.title, course.url, course.cover_url, course.summary,
                    course.instructor, course.published_at, course.duration_seconds, course.view_count,
                    course.quality_score, course.difficulty, course.language, int(course.is_free),
                    course.content, content_hash, json.dumps(course.raw, ensure_ascii=False), now,
                ),
            )

            connection.executemany(
                "INSERT OR REPLACE INTO course_skills(course_id, skill, relevance) VALUES (?, ?, ?)",
                [(course.course_id, skill, 1.0) for skill in dict.fromkeys(course.skills)],
            )
            skill_rows = connection.execute(
                "SELECT skill FROM course_skills WHERE course_id = ? ORDER BY skill", (course.course_id,),
            ).fetchall()
            connection.execute("DELETE FROM courses_fts WHERE course_id = ?", (course.course_id,))
            connection.execute(
                "INSERT INTO courses_fts(course_id, title, summary, content, skills) VALUES (?, ?, ?, ?, ?)",
                (course.course_id, course.title, course.summary, course.content, " ".join(row[0] for row in skill_rows)),
            )

    def get_course(self, course_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM courses WHERE course_id = ?", (course_id,)).fetchone()
        return dict(row) if row else None

    def courses_for_skill(self, skill: str, limit: int = 20) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT c.*, cs.relevance, COALESCE(h.status, 'unknown') AS link_status FROM courses c
                JOIN course_skills cs ON cs.course_id = c.course_id
                LEFT JOIN course_link_health h ON h.course_id = c.course_id
                WHERE lower(cs.skill) = lower(?) AND COALESCE(h.status, 'unknown') != 'broken'
                ORDER BY c.quality_score DESC, c.view_count DESC LIMIT ?""",
                (skill, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_course_links(self, limit: int = 200) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT course_id, source, url FROM courses ORDER BY updated_at DESC LIMIT ?", (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_link_health(self, course_id: str, status: str, http_status: int | None) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO course_link_health VALUES (?, ?, ?, ?)",
                (course_id, status, http_status, datetime.now(UTC).isoformat()),
            )

    def save_route(self, route: LearningRoute) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO learning_routes VALUES (?, ?, ?, ?)",
                (route.route_id, route.job_key, route.model_dump_json(), route.generated_at),
            )

    def get_route(self, route_id: str) -> LearningRoute | None:
        with self.connect() as connection:
            row = connection.execute("SELECT payload FROM learning_routes WHERE route_id = ?", (route_id,)).fetchone()
        return LearningRoute.model_validate_json(row["payload"]) if row else None

    def stats(self) -> dict:
        with self.connect() as connection:
            jobs = connection.execute("SELECT COUNT(*) FROM job_profiles").fetchone()[0]
            courses = connection.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
            skills = connection.execute("SELECT COUNT(DISTINCT skill) FROM course_skills").fetchone()[0]
            routes = connection.execute("SELECT COUNT(*) FROM learning_routes").fetchone()[0]
        return {"jobs": jobs, "courses": courses, "covered_skills": skills, "routes": routes}
