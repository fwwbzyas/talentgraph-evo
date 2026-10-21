-- 数据采集与清洗流水线 — 数据库初始化
-- PostgreSQL Schema
-- 版本: v1.0.0

CREATE TABLE IF NOT EXISTS raw_job_descriptions (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    source_url      TEXT NOT NULL,
    title           TEXT NOT NULL,
    company         TEXT,
    description     TEXT NOT NULL,
    required_skills_raw TEXT[] DEFAULT '{}',
    optional_skills_raw TEXT[] DEFAULT '{}',
    salary_range    TEXT,
    location        TEXT,
    experience      TEXT,
    education       TEXT,
    publish_date    TEXT,
    crawl_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_html        TEXT
);

CREATE TABLE IF NOT EXISTS cleaned_job_descriptions (
    id              TEXT PRIMARY KEY,
    raw_id          TEXT NOT NULL REFERENCES raw_job_descriptions(id),
    source          TEXT NOT NULL,
    title           TEXT NOT NULL,
    company         TEXT,
    description_clean TEXT NOT NULL,
    skills          JSONB DEFAULT '[]',
    quality_score   FLOAT NOT NULL CHECK (quality_score >= 0 AND quality_score <= 100),
    quality_level   TEXT NOT NULL DEFAULT 'medium',
    is_duplicate    BOOLEAN DEFAULT FALSE,
    is_plagiarized  BOOLEAN DEFAULT FALSE,
    is_ai_generated BOOLEAN DEFAULT FALSE,
    freshness_weight FLOAT DEFAULT 1.0,
    cleaning_trace  JSONB DEFAULT '{}',
    cleaned_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_source ON raw_job_descriptions(source);
CREATE INDEX IF NOT EXISTS idx_raw_title ON raw_job_descriptions(title);
CREATE INDEX IF NOT EXISTS idx_raw_crawl ON raw_job_descriptions(crawl_timestamp);
CREATE INDEX IF NOT EXISTS idx_cleaned_raw_id ON cleaned_job_descriptions(raw_id);
CREATE INDEX IF NOT EXISTS idx_cleaned_quality ON cleaned_job_descriptions(quality_score);
CREATE INDEX IF NOT EXISTS idx_cleaned_level ON cleaned_job_descriptions(quality_level);
