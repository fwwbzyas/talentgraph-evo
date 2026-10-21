from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
import gzip
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import random
import re
import sqlite3
import tempfile
from typing import Any
from zipfile import ZipFile


DATASET_VERSION = "temporal-jd-100-v1.0"
SEED = 20260905
DOMAINS = ("人工智能", "大数据", "智能系统", "物联网")
QUOTA = {domain: 25 for domain in DOMAINS}
REAL_SOURCES = {"zhaopin", "boss", "51job", "liepin"}
SCENARIO_COUNTS = {
    "stable_control": 15,
    "gradual_skill_growth": 25,
    "skill_transition": 20,
    "salary_progression": 15,
    "requirement_tightening": 10,
    "offline_reactivation": 10,
    "multi_field_transition": 5,
}
SKILL_POOLS = {
    "人工智能": ["RAG", "LangGraph", "向量数据库", "Agent", "评测体系", "OpenTelemetry", "Kubernetes"],
    "大数据": ["Flink", "Spark", "Kafka", "Iceberg", "数据仓库", "可观测性", "Kubernetes"],
    "智能系统": ["Kubernetes", "Docker", "Prometheus", "OpenTelemetry", "自动化测试", "边缘计算", "ROS"],
    "物联网": ["MQTT", "RTOS", "嵌入式 Linux", "边缘计算", "时序数据库", "OTA", "设备接入"],
}
REMOVAL_ALIASES = {
    "RAG": ["retrieval augmented"], "PyTorch": ["pytorch"], "TensorFlow": ["tensorflow"],
    "Java": ["java"], "C++": ["cpp"], "Linux": ["embedded linux", "嵌入式 linux"],
    "LangChain": ["langchain"], "LangGraph": ["langgraph"],
    "自动化测试": ["test automation"], "Flink": ["flink"], "Spark": ["spark"],
    "Kafka": ["kafka"], "RTOS": ["rtos"], "Kubernetes": ["k8s"],
    "Agent": ["ai agent", "agentic", "智能体"], "Docker": ["docker"],
    "MQTT": ["mqtt"], "OpenTelemetry": ["opentelemetry"], "Prometheus": ["prometheus"],
}
DIFF_FIELDS = (
    "title", "company", "city", "district", "salary_min_k", "salary_max_k", "salary_months",
    "experience_min_years", "experience_max_years", "education", "skill_tags",
    "responsibilities", "requirements", "job_status",
)


def month_id(start_year: int, start_month: int, offset: int) -> str:
    value = start_year * 12 + start_month - 1 + offset
    return f"{value // 12:04d}-{value % 12 + 1:02d}"


def iso_time(period: str) -> str:
    return f"{period}-01T09:00:00+08:00"


def digest(value: str, length: int = 16) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:length]


def sanitize_text(value: str, company: str | None, alias: str) -> str:
    text = str(value or "")
    if company:
        text = re.sub(re.escape(company), alias, text, flags=re.IGNORECASE)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[邮箱已脱敏]", text)
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已脱敏]", text)
    text = re.sub(r"https?://\S+", "[链接已脱敏]", text)
    return text


def open_database(source: Path):
    if source.suffix.lower() != ".zip":
        return source, None
    temporary_root = os.getenv("TEMPORAL_TEST_TMP")
    temporary = tempfile.TemporaryDirectory(
        prefix="temporal-jd-",
        dir=temporary_root or None,
    )
    with ZipFile(source) as archive:
        member = next((name for name in archive.namelist() if name.endswith(("talentgraph.db", "talentgraph.snapshot.db"))), None)
        if not member:
            temporary.cleanup()
            raise RuntimeError(f"{source} 中没有 SQLite 数据库")
        target = Path(temporary.name) / "source.db"
        with archive.open(member) as source_file, target.open("wb") as target_file:
            while chunk := source_file.read(1024 * 1024):
                target_file.write(chunk)
    return target, temporary


def load_candidates(source: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    db_path, temporary = open_database(source)
    try:
        connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            rows = connection.execute("SELECT payload FROM job_assets").fetchall()
        finally:
            connection.close()
    finally:
        if temporary:
            temporary.cleanup()

    all_items = [json.loads(payload) for (payload,) in rows]
    rejected = Counter()
    candidates: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for item in all_items:
        platform = str(item.get("source_platform") or "")
        metadata = item.get("metadata") or {}
        if platform not in REAL_SOURCES:
            rejected["non_real_source"] += 1
            continue
        if metadata.get("synthetic") or metadata.get("is_simulated") or metadata.get("synthetic_temporal_test"):
            rejected["simulation_flag"] += 1
            continue
        if item.get("domain") not in DOMAINS:
            rejected["domain"] += 1
            continue
        if item.get("job_status", "active") != "active":
            rejected["offline"] += 1
            continue
        if len(item.get("content") or "") < 300:
            rejected["short_content"] += 1
            continue
        if len(item.get("skill_tags") or []) < 3:
            rejected["few_skills"] += 1
            continue
        if not item.get("company") or not item.get("source_url"):
            rejected["missing_provenance"] += 1
            continue
        fingerprint = str(item.get("dedup_hash") or digest(json.dumps(item, sort_keys=True, ensure_ascii=False)))
        if fingerprint in seen_hashes:
            rejected["duplicate"] += 1
            continue
        seen_hashes.add(fingerprint)
        candidates.append(item)
    return candidates, {
        "source_job_count": len(all_items),
        "eligible_job_count": len(candidates),
        "excluded_counts": dict(rejected),
    }


def select_baseline(candidates: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for domain, count in QUOTA.items():
        pool = [item for item in candidates if item.get("domain") == domain]
        pool.sort(key=lambda item: digest(f"{seed}|{item.get('source_id')}|{item.get('dedup_hash')}", 64))
        if len(pool) < count:
            raise RuntimeError(f"{domain} 合格真实 JD 只有 {len(pool)} 条，无法抽取 {count} 条")
        selected.extend(pool[:count])
    selected.sort(key=lambda item: digest(f"scenario|{seed}|{item.get('source_id')}", 64))
    return selected


def assign_scenarios(items: list[dict[str, Any]]) -> dict[str, str]:
    if len(items) != sum(SCENARIO_COUNTS.values()):
        raise RuntimeError("场景数量与基线数量不一致")
    # Additive skill scenarios must start from the least crowded skill profiles.
    # Otherwise the simulator itself can cross the production governance rule's
    # skill-inflation boundary and turn a valid evolution signal into manual review.
    ordered = sorted(
        items,
        key=lambda item: (
            len(item.get("skill_tags") or []),
            digest(f"scenario|{SEED}|{item.get('source_id')}", 64),
        ),
    )
    additive = [
        *("gradual_skill_growth" for _ in range(SCENARIO_COUNTS["gradual_skill_growth"])),
        *("multi_field_transition" for _ in range(SCENARIO_COUNTS["multi_field_transition"])),
    ]
    remaining = [
        scenario
        for scenario, count in SCENARIO_COUNTS.items()
        if scenario not in {"gradual_skill_growth", "multi_field_transition"}
        for _ in range(count)
    ]
    assignments: dict[str, str] = {}
    for item, scenario in zip(ordered[: len(additive)], additive, strict=True):
        assignments[str(item["source_id"])] = scenario
    tail = sorted(
        ordered[len(additive):],
        key=lambda item: digest(f"tail-scenario|{SEED}|{item.get('source_id')}", 64),
    )
    for item, scenario in zip(tail, remaining, strict=True):
        assignments[str(item["source_id"])] = scenario
    return assignments


def anonymized_baseline(item: dict[str, Any], seed: int) -> dict[str, Any]:
    original_id = str(item["source_id"])
    token = digest(f"{seed}|{original_id}", 12)
    company_alias = f"测试企业-{token[:6].upper()}"
    platform = str(item["source_platform"])
    content = sanitize_text(item.get("content") or "", item.get("company"), company_alias)
    raw_content = sanitize_text(item.get("raw_content") or content, item.get("company"), company_alias)
    return {
        "source_id": f"temporal-{token}",
        "source_platform": platform,
        "source_url": f"https://temporal-test.invalid/{platform}/{token}",
        "title": item.get("title"),
        "company": company_alias,
        "company_industry": item.get("company_industry"),
        "company_size": item.get("company_size"),
        "city": item.get("city"),
        "district": item.get("district"),
        "content": content,
        "raw_content": raw_content,
        "domain": item.get("domain"),
        "salary_min_k": item.get("salary_min_k"),
        "salary_max_k": item.get("salary_max_k"),
        "salary_months": item.get("salary_months") or 12,
        "currency": item.get("currency") or "CNY",
        "experience_min_years": item.get("experience_min_years"),
        "experience_max_years": item.get("experience_max_years"),
        "education": item.get("education"),
        "employment_type": item.get("employment_type") or "full_time",
        "skill_tags": list(item.get("skill_tags") or []),
        "responsibilities": list(item.get("responsibilities") or []),
        "requirements": list(item.get("requirements") or []),
        "benefits": list(item.get("benefits") or []),
        "job_status": "active",
        "collection_mode": "live",
        "metadata": {
            "dataset_version": DATASET_VERSION,
            "synthetic_temporal_test": True,
            "production_write_forbidden": True,
            "baseline_from_real_jd": True,
            "original_record_digest": digest(original_id, 24),
            "original_source_platform": platform,
        },
    }


def choose_new_skill(state: dict[str, Any], event_number: int) -> str:
    current = set(state.get("skill_tags") or [])
    pool = SKILL_POOLS[state["domain"]]
    available = [skill for skill in pool if skill not in current]
    return (available or pool)[event_number % len(available or pool)]


def add_skill(state: dict[str, Any], skill: str) -> None:
    state["skill_tags"] = list(dict.fromkeys([*(state.get("skill_tags") or []), skill]))
    state["content"] = f"{state['content']}\n任职要求补充：具备 {skill} 的工程实践经验，并能说明可复核的项目证据。"
    state["requirements"] = list(dict.fromkeys([*(state.get("requirements") or []), f"具备 {skill} 的工程实践经验"] ))


def replace_skill_mentions(value: str, old: str, new: str) -> str:
    aliases = sorted({old, *REMOVAL_ALIASES.get(old, [])}, key=len, reverse=True)
    output = value
    for alias in aliases:
        if alias.isascii() and alias.replace("+", "").replace(" ", "").isalnum():
            pattern = rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])"
        else:
            pattern = re.escape(alias)
        output = re.sub(pattern, new, output, flags=re.IGNORECASE)
    return output


def update_salary_marker(state: dict[str, Any]) -> None:
    marker = f"测试薪酬区间：{state.get('salary_min_k') or 0}-{state.get('salary_max_k') or 0}K。"
    pattern = re.compile(r"\n测试薪酬区间：[^\n]*")
    state["content"] = pattern.sub("", state["content"]) + "\n" + marker


def apply_event(state: dict[str, Any], scenario: str, month_index: int, event_number: int) -> dict[str, Any]:
    expected_fields: list[str] = []
    added_skills: list[str] = []
    removed_skills: list[str] = []
    event_type = scenario

    if scenario in {"gradual_skill_growth", "multi_field_transition"}:
        skill = choose_new_skill(state, event_number)
        if skill not in state.get("skill_tags", []):
            add_skill(state, skill)
            expected_fields.append("skill_tags")
            added_skills.append(skill)

    if scenario == "skill_transition":
        skill = choose_new_skill(state, event_number)
        old_candidates = [
            value for value in state.get("skill_tags", [])
            if value != skill
            and replace_skill_mentions(str(state.get("title") or ""), value, "__REMOVED__") == str(state.get("title") or "")
            and replace_skill_mentions(skill, value, "__REMOVED__") == skill
            and all(
                other == value or replace_skill_mentions(str(other), value, "__REMOVED__") == str(other)
                for other in state.get("skill_tags", [])
            )
        ]
        if not old_candidates:
            old_candidates = [value for value in state.get("skill_tags", []) if value != skill]
        old = old_candidates[event_number % len(old_candidates)] if old_candidates else None
        if old:
            state["skill_tags"] = [value for value in state["skill_tags"] if value != old]
            state["content"] = replace_skill_mentions(state["content"], old, skill)
            state["requirements"] = [replace_skill_mentions(value, old, skill) for value in state.get("requirements", [])]
            removed_skills.append(old)
        add_skill(state, skill)
        expected_fields.append("skill_tags")
        added_skills.append(skill)

    if scenario in {"salary_progression", "multi_field_transition"}:
        for field in ("salary_min_k", "salary_max_k"):
            value = state.get(field)
            if value is not None:
                updated = max(int(value) + 1, int(round(value * 1.06)))
                if updated != value:
                    state[field] = updated
                    expected_fields.append(field)
        if not any(state.get(field) is not None for field in ("salary_min_k", "salary_max_k")):
            state["salary_min_k"], state["salary_max_k"] = 15, 25
            expected_fields.extend(["salary_min_k", "salary_max_k"])
        update_salary_marker(state)

    if scenario in {"requirement_tightening", "multi_field_transition"}:
        before = state.get("experience_min_years")
        updated = min(15, int(before or 0) + 1)
        state["experience_min_years"] = updated
        if updated != before:
            expected_fields.append("experience_min_years")
        line = f"经验要求测试更新：至少 {state['experience_min_years']} 年相关工程经验。"
        state["content"] = re.sub(r"\n经验要求测试更新：[^\n]*", "", state["content"]) + "\n" + line
        state["requirements"] = list(dict.fromkeys([*(state.get("requirements") or []), line]))

    if scenario == "offline_reactivation":
        state["job_status"] = "offline" if state.get("job_status") == "active" else "active"
        state["content"] = re.sub(r"\n岗位状态测试标记：[^\n]*", "", state["content"]) + f"\n岗位状态测试标记：{state['job_status']}。"
        expected_fields.append("job_status")
        event_type = state["job_status"]

    return {
        "event_type": event_type,
        "expected_changed_fields": sorted(set(expected_fields)),
        "expected_added_skills": sorted(set(added_skills)),
        "expected_removed_skills": sorted(set(removed_skills)),
        "month_index": month_index,
    }


def event_due(scenario: str, month_index: int, phase: int) -> bool:
    if scenario == "stable_control":
        return False
    interval = {
        "gradual_skill_growth": 3,
        "skill_transition": 4,
        "salary_progression": 6,
        "requirement_tightening": 5,
        "multi_field_transition": 3,
    }.get(scenario)
    if interval:
        return (month_index - 1) % interval == phase % interval
    if scenario == "offline_reactivation":
        offline_month = phase % 6 + 2
        return month_index in {offline_month, offline_month + 3}
    return False


def write_jsonl(path: Path, records: list[dict[str, Any]], *, compressed: bool = False) -> None:
    if compressed:
        with path.open("wb") as raw_handle:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as gzip_handle:
                with io.TextIOWrapper(gzip_handle, encoding="utf-8", newline="\n") as handle:
                    for record in records:
                        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def generate(source: Path, output: Path, seed: int = SEED) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    candidates, source_stats = load_candidates(source)
    selected = select_baseline(candidates, seed)
    assignments = assign_scenarios(selected)
    periods = [month_id(2025, 9, offset) for offset in range(12)]
    rows: list[dict[str, Any]] = []
    truth: list[dict[str, Any]] = []
    baseline_rows: list[dict[str, Any]] = []
    outcome_counts = Counter()
    event_counts = Counter()

    for source_item in selected:
        original_id = str(source_item["source_id"])
        state = anonymized_baseline(source_item, seed)
        scenario = assignments[original_id]
        phase = int(digest(f"phase|{seed}|{original_id}", 8), 16)
        event_number = 0
        for month_index, period in enumerate(periods):
            expectation = {
                "event_type": "baseline" if month_index == 0 else "unchanged",
                "expected_changed_fields": [],
                "expected_added_skills": [],
                "expected_removed_skills": [],
                "month_index": month_index,
            }
            if month_index > 0 and event_due(scenario, month_index, phase):
                event_number += 1
                expectation = apply_event(state, scenario, month_index, event_number)
            outcome = "new" if month_index == 0 else "updated" if expectation["expected_changed_fields"] else "unchanged"
            timestamp = iso_time(period)
            raw = deepcopy(state)
            # The production normalizer deliberately prefers raw_content over
            # content. Keep both views synchronized so the simulated posting
            # actually contains every declared change.
            raw["raw_content"] = raw["content"]
            raw["published_at"] = timestamp
            raw["changed_at"] = timestamp if outcome != "unchanged" else None
            raw["metadata"] = {**raw["metadata"], "scenario": scenario, "observation_period": period}
            record_id = f"{raw['source_id']}:{period}"
            row = {
                "record_id": record_id,
                "dataset_version": DATASET_VERSION,
                "period": period,
                "observed_at": timestamp,
                "scenario": scenario,
                "expected_outcome": outcome,
                "raw_item": raw,
            }
            rows.append(row)
            truth_record = {
                "record_id": record_id,
                "period": period,
                "source_id": f"{raw['source_platform']}:{raw['source_id']}",
                "scenario": scenario,
                "expected_outcome": outcome,
                **expectation,
            }
            truth.append(truth_record)
            outcome_counts[outcome] += 1
            if outcome == "updated":
                event_counts[expectation["event_type"]] += 1
            if month_index == 0:
                baseline_rows.append(row)

    write_jsonl(output / "baseline_100.jsonl", baseline_rows)
    write_jsonl(output / "temporal_raw_12_months.jsonl.gz", rows, compressed=True)
    write_jsonl(output / "ground_truth.jsonl", truth)
    dataset_hash = sha256((output / "temporal_raw_12_months.jsonl.gz").read_bytes()).hexdigest()
    manifest = {
        "dataset_version": DATASET_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "seed": seed,
        "purpose": "100条真实JD基线的未来12个月岗位变化捕捉测试，不用于真实市场结论",
        "is_synthetic_temporal_test": True,
        "production_write_forbidden": True,
        "source_database": source.name,
        "source_database_sha256": sha256(source.read_bytes()).hexdigest(),
        "dataset_sha256": dataset_hash,
        "baseline_count": len(baseline_rows),
        "periods": periods,
        "observation_count": len(rows),
        "domain_counts": dict(Counter(row["raw_item"]["domain"] for row in baseline_rows)),
        "source_counts": dict(Counter(row["raw_item"]["source_platform"] for row in baseline_rows)),
        "scenario_counts": SCENARIO_COUNTS,
        "expected_outcome_counts": dict(outcome_counts),
        "expected_event_counts": dict(event_counts),
        "selection_policy": {
            "real_sources_only": sorted(REAL_SOURCES),
            "balanced_domain_quota": QUOTA,
            "minimum_content_characters": 300,
            "minimum_skill_count": 3,
            "requires_company_and_source_url": True,
            "deduplicated_by": "dedup_hash",
            "deterministic_hash_sampling": True,
            "pseudonymization": ["company", "source_id", "source_url", "phone", "email", "url"],
        },
        "source_stats": source_stats,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="生成隔离的100条JD、未来12个月时间渐进测试数据集")
    parser.add_argument("--source", type=Path, required=True, help="talentgraph.db 或 talentgraph-db.zip")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "data")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    manifest = generate(args.source.resolve(), args.output.resolve(), args.seed)
    print(json.dumps({
        "dataset_version": manifest["dataset_version"],
        "baseline_count": manifest["baseline_count"],
        "observation_count": manifest["observation_count"],
        "expected_outcome_counts": manifest["expected_outcome_counts"],
        "output": str(args.output.resolve()),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
