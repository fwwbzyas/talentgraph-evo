from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SOURCE_IDS = ("boss", "zhaopin")
TARGET_QUERIES = (
    "AI Agent 工程师", "大模型应用工程师", "RAG 工程师", "机器学习工程师",
    "算法工程师", "多模态工程师", "模型评测工程师", "AI 平台工程师",
    "大数据开发工程师", "实时计算工程师", "Flink 工程师", "数据平台工程师",
    "数据治理工程师", "数据仓库工程师", "湖仓架构师", "智能系统工程师",
    "机器人软件工程师", "边缘智能工程师", "自动驾驶系统工程师",
    "物联网平台工程师", "物联网嵌入式工程师", "IoT 工程师",
    "边缘网关工程师", "固件工程师",
)
STRATEGY_FIELDS = (
    "enabled", "mode", "min_interval_minutes", "max_interval_minutes", "items_per_run",
    "discovery_ratio", "revisit_after_hours", "cities", "job_queries",
)


def api(base_url: str, path: str, method: str = "GET", payload: dict | None = None) -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = Request(
        f"{base_url.rstrip('/')}{path}", data=body, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"API {method} {path} failed: {exc.read().decode('utf-8', 'replace')}") from exc
    except URLError as exc:
        raise RuntimeError(f"TalentGraph API is unavailable at {base_url}") from exc


def strategy_payload(strategy: dict, *, enabled: bool | None = None) -> dict:
    sources = {}
    for source_id, source in strategy["sources"].items():
        values = {key: source[key] for key in STRATEGY_FIELDS if key in source}
        if enabled is not None:
            values["enabled"] = enabled if source_id in SOURCE_IDS else False
        sources[source_id] = values
    return {"enabled": any(item["enabled"] for item in sources.values()), "sources": sources}


def paused_strategy_payload(strategy: dict) -> dict:
    payload = strategy_payload(strategy)
    for source_id, source in payload["sources"].items():
        source["enabled"] = source_id in SOURCE_IDS
        if source_id in SOURCE_IDS:
            source["min_interval_minutes"] = 10080
            source["max_interval_minutes"] = 10080
    payload["enabled"] = True
    return payload


def save_checkpoint(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.stem}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    for attempt in range(12):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 11:
                raise
            time.sleep(0.1 * (attempt + 1))


def wait_for_run(base_url: str, run_id: str, poll_seconds: float) -> dict:
    while True:
        run = api(base_url, f"/api/data/collection-runs/{run_id}")
        if run["status"] != "running":
            return run
        time.sleep(poll_seconds)


def wait_for_authentication(args, checkpoint: dict) -> None:
    required = set(selected_sources(args))
    for source_id in required:
        api(args.api_url, f"/api/data/browser-sessions/{source_id}/start", "POST")
    deadline = time.monotonic() + args.auth_wait_seconds if args.auth_wait_seconds > 0 else None
    while True:
        statuses = {
            item["source_id"]: item
            for item in api(args.api_url, "/api/data/browser-sessions").get("items", [])
        }
        waiting = [source_id for source_id in required if statuses.get(source_id, {}).get("authentication") != "ready"]
        if not waiting:
            return
        checkpoint.update({
            "status": "waiting_for_login",
            "waiting_sources": waiting,
            "updated_at": datetime.now().isoformat(),
        })
        save_checkpoint(args.checkpoint, checkpoint)
        if deadline is not None and time.monotonic() >= deadline:
            raise RuntimeError(f"login timeout for: {', '.join(waiting)}")
        time.sleep(2)


def recover_after_failure(args, checkpoint: dict, key: str, error: str) -> None:
    retries = checkpoint.setdefault("retry_counts", {})
    retries[key] = int(retries.get(key, 0)) + 1
    delay = min(args.max_retry_seconds, args.retry_seconds * (2 ** min(retries[key] - 1, 5)))
    checkpoint.update({
        "status": "reconnecting",
        "last_error": error,
        "retry_in_seconds": delay,
        "updated_at": datetime.now().isoformat(),
    })
    save_checkpoint(args.checkpoint, checkpoint)
    print(f"retry {key} in {delay:.0f}s: {error}", flush=True)
    time.sleep(delay)
    wait_for_authentication(args, checkpoint)


def selected_sources(args) -> tuple[str, ...]:
    return SOURCE_IDS if args.sources == "all" else tuple(args.sources.split(","))


def target_cities(args, source: dict) -> list[str]:
    if args.city_scope == "all":
        cities = [city for city in source.get("options", {}).get("cities", []) if city != "全国"]
        if cities:
            return cities
    return source.get("cities") or ["全国"]


def build_work_items(args, original_strategy: dict) -> list[dict[str, str]]:
    stages = ["discovery", "monitor"] if args.mode == "both" else [args.mode]
    return [
        {"stage": stage, "source_id": source_id, "city": city, "query": query}
        for stage in stages
        for source_id in selected_sources(args)
        for city in target_cities(args, original_strategy["sources"][source_id])
        for query in TARGET_QUERIES
    ]


def run_cycle(args, checkpoint: dict, original_strategy: dict) -> dict:
    completed = set(checkpoint.get("completed", []))
    active_key = checkpoint.get("active_key")
    totals = checkpoint.setdefault("totals", {"runs": 0, "scanned": 0, "accepted": 0, "new": 0, "updated": 0})
    work_items = checkpoint.setdefault("work_items", build_work_items(args, original_strategy))
    checkpoint["total_count"] = len(work_items)

    for item in work_items:
        stage = item["stage"]
        source_id = item["source_id"]
        city = item["city"]
        query = item["query"]
        key = f"{stage}|{source_id}|{city}|{query}"
        if key in completed:
            continue
        reset_cursor = active_key != key or checkpoint.get("status") == "attention_required"
        checkpoint.update({
            "status": "running", "stage": stage, "source_id": source_id,
            "city": city, "query": query, "active_key": key,
            "updated_at": datetime.now().isoformat(),
        })
        save_checkpoint(args.checkpoint, checkpoint)
        while True:
            request_payload = {
                "source_ids": [source_id],
                "max_items_per_source": args.batch_size,
                "lookback_hours": 24 * 90,
                "min_job_quality": args.min_quality,
                "min_signal_quality": 55,
                "persist": True,
                "query_overrides": {source_id: [query]},
                "city_overrides": {source_id: [city]},
                "collection_mode_override": "hybrid" if stage == "monitor" else stage,
                "full_scan_chunk": True,
                "reset_scan_cursor": reset_cursor,
            }
            queued = api(args.api_url, "/api/data/collect", "POST", request_payload)
            run = wait_for_run(args.api_url, queued["run_id"], args.poll_seconds)
            result = run["source_results"][0]
            totals["runs"] += 1
            totals["scanned"] += int(result.get("scanned", 0))
            totals["accepted"] += int(result.get("accepted", 0))
            totals["new"] += int(run.get("new_count", 0))
            totals["updated"] += int(run.get("updated_count", 0))
            checkpoint["last_run"] = {
                "run_id": run["run_id"], "status": run["status"],
                "scanned": result.get("scanned", 0), "accepted": result.get("accepted", 0),
                "duration_ms": result.get("duration_ms", 0), "error": result.get("error"),
            }
            checkpoint["updated_at"] = datetime.now().isoformat()
            save_checkpoint(args.checkpoint, checkpoint)
            print(
                f"[{source_id}] {stage} | {city} | {query} | "
                f"scanned={result.get('scanned', 0)} accepted={result.get('accepted', 0)} "
                f"end={result.get('reached_end', False)} duration={result.get('duration_ms', 0) / 1000:.1f}s",
                flush=True,
            )
            if run["status"] == "failed" or result.get("status") == "failed":
                error = result.get("error") or f"{source_id} collection failed"
                recover_after_failure(args, checkpoint, key, error)
                reset_cursor = True
                continue
            if result.get("reached_end"):
                break
            reset_cursor = False
        completed.add(key)
        checkpoint.setdefault("retry_counts", {}).pop(key, None)
        checkpoint["completed"] = sorted(completed)
        checkpoint.setdefault("completion_evidence", {})[key] = {
            "run_id": run["run_id"],
            "end_reason": result.get("end_reason"),
            "scanned": result.get("scanned", 0),
            "accepted": result.get("accepted", 0),
            "completed_at": datetime.now().isoformat(),
        }
        checkpoint["active_key"] = None
        active_key = None
        save_checkpoint(args.checkpoint, checkpoint)
    checkpoint.update({"status": "completed", "active_key": None, "completed_at": datetime.now().isoformat()})
    save_checkpoint(args.checkpoint, checkpoint)
    return checkpoint


def main() -> int:
    parser = argparse.ArgumentParser(description="Crawl complete BOSS and Zhaopin result sets with checkpoint resume.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--mode", choices=("discovery", "monitor", "both"), default="both")
    parser.add_argument("--sources", default="all", help="all, boss, zhaopin, or a comma-separated subset")
    parser.add_argument("--city-scope", choices=("all", "configured"), default="all")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--min-quality", type=float, default=65)
    parser.add_argument("--poll-seconds", type=float, default=2)
    parser.add_argument("--auth-wait-seconds", type=float, default=1800)
    parser.add_argument("--retry-seconds", type=float, default=5)
    parser.add_argument("--max-retry-seconds", type=float, default=300)
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--monitor-interval-hours", type=float, default=24)
    parser.add_argument("--checkpoint", type=Path, default=Path("data/full_recruitment_crawl_state.json"))
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--rebuild-work-items", action="store_true")
    args = parser.parse_args()
    requested_sources = selected_sources(args)
    if not requested_sources or any(source_id not in SOURCE_IDS for source_id in requested_sources):
        parser.error("--sources must contain only boss and/or zhaopin")

    if args.fresh and args.checkpoint.exists():
        args.checkpoint.unlink()
    checkpoint = json.loads(args.checkpoint.read_text(encoding="utf-8")) if args.checkpoint.exists() else {
        "status": "starting", "mode": args.mode, "completed": [], "created_at": datetime.now().isoformat(),
    }
    original_strategy = checkpoint.get("original_strategy") or api(args.api_url, "/api/data/strategy")
    checkpoint["original_strategy"] = original_strategy
    if args.rebuild_work_items:
        checkpoint["work_items"] = build_work_items(args, original_strategy)
        checkpoint["total_count"] = len(checkpoint["work_items"])
        valid_keys = {
            f"{item['stage']}|{item['source_id']}|{item['city']}|{item['query']}"
            for item in checkpoint["work_items"]
        }
        checkpoint["completed"] = [key for key in checkpoint.get("completed", []) if key in valid_keys]
        checkpoint["completion_evidence"] = {
            key: value for key, value in checkpoint.get("completion_evidence", {}).items() if key in valid_keys
        }
        checkpoint["active_key"] = None
        checkpoint["totals"] = {"runs": 0, "scanned": 0, "accepted": 0, "new": 0, "updated": 0}
        checkpoint["last_run"] = None
        checkpoint.pop("last_error", None)
        checkpoint.pop("retry_in_seconds", None)
    save_checkpoint(args.checkpoint, checkpoint)
    wait_for_authentication(args, checkpoint)
    api(args.api_url, "/api/data/strategy", "PUT", paused_strategy_payload(original_strategy))
    try:
        result = run_cycle(args, checkpoint, original_strategy)
        print(json.dumps(result["totals"], ensure_ascii=False), flush=True)
        while args.continuous:
            next_cycle = datetime.now() + timedelta(hours=args.monitor_interval_hours)
            checkpoint.update({
                "status": "waiting_next_monitor",
                "next_cycle_at": next_cycle.isoformat(),
                "updated_at": datetime.now().isoformat(),
            })
            save_checkpoint(args.checkpoint, checkpoint)
            while datetime.now() < next_cycle:
                time.sleep(min(60, max(1, (next_cycle - datetime.now()).total_seconds())))
            args.mode = "monitor"
            checkpoint = {
                "status": "starting", "mode": "monitor", "cycle_type": "full_monitor",
                "completed": [], "created_at": datetime.now().isoformat(),
                "original_strategy": original_strategy,
            }
            save_checkpoint(args.checkpoint, checkpoint)
            wait_for_authentication(args, checkpoint)
            result = run_cycle(args, checkpoint, original_strategy)
            print(json.dumps(result["totals"], ensure_ascii=False), flush=True)
        return 0
    finally:
        api(args.api_url, "/api/data/strategy", "PUT", strategy_payload(original_strategy))


if __name__ == "__main__":
    raise SystemExit(main())
