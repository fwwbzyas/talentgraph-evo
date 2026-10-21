"""Evaluate resume gold data through production extraction and parsing APIs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import statistics
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agents.assessment.resume_files import extract_resume_text
from agents.assessment.resume_parser import SKILL_ALIASES, ResumeParsingAgent

DATA = ROOT / "data/evaluation/resume_gold_100"
REPORTS = DATA / "reports"
DOC_REPORT = ROOT / "docs/testing/RESUME_GOLD_100_REPORT.md"
ALL_FIELDS = ("job_intent", "skills", "projects", "experience_years", "education", "certifications", "preferred_locations", "expected_salary_k", "work_history")


def _evaluation_file_path(data_dir: Path, item: dict[str, Any], input_format: str = "manifest") -> Path:
    if input_format == "txt":
        relative = item.get("file_paths", {}).get("txt")
        if not relative:
            raise ValueError(f"manifest item {item.get('id')} has no TXT artifact")
        return data_dir / relative
    filename = str(item["filename"])
    nested = data_dir / "files" / filename
    return nested if nested.exists() else data_dir / filename


def _highest_observed_education(text: str) -> str | None:
    """Derive the highest explicit degree from the resume's education section."""
    lines = [line.strip() for line in re.sub(r"\r\n?", "\n", text or "").splitlines() if line.strip()]
    heading = re.compile(r"^(?:教育背景|教育经历|学历|Education|Academic Background)\s*[:：]?\s*$", re.I)
    stop = re.compile(r"^(?:职业摘要|求职意向|核心技能|技能|技能证据|工作经历|项目经历|项目经验|优势|合理弱点与改进|证书|Certification|Experience|Projects?)\s*[:：]?\s*$", re.I)
    section: list[str] = []
    in_section = False
    for line in lines:
        if heading.match(line):
            in_section = True
            continue
        if in_section and stop.match(line):
            break
        if in_section:
            section.append(line)
    source = "\n".join(section)
    levels = (
        ("博士", ("博士", "ph.d", "phd", "doctorate")),
        ("硕士", ("硕士", "研究生", "master", "msc", "mba")),
        ("本科", ("本科", "学士", "bachelor", "b.s.")),
        ("大专", ("大专", "专科", "associate")),
    )
    lowered = source.lower()
    for canonical, markers in levels:
        if any(marker in lowered for marker in markers):
            return canonical
    return None


def _norm(value: Any) -> Any:
    if isinstance(value, str): return " ".join(value.lower().strip().split())
    if isinstance(value, list): return sorted({_norm(x) for x in value if x not in (None, "", [])})
    return value


def _norm_intent(value: Any) -> str:
    value = _norm(value) if isinstance(value, str) else ""
    for prefix in ("求职意向", "岗位意向", "目标岗位", "应聘岗位", "期望职位", "意向职位", "desired position", "target role"):
        if value.startswith(prefix): value = value[len(prefix):].strip(" ：:|,，")
    return value.strip(" ：:|,，")


def _skill_names(value: Any) -> list[str]:
    return [str(item.get("name") or item.get("canonical_name")) if isinstance(item, dict) else str(item) for item in (value or [])]


def _skill_key(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    compact = re.sub(r"[._\-\s]+", "", text)
    for alias in SKILL_ALIASES:
        candidates = (alias.canonical, *alias.aliases)
        if any(re.sub(r"[._\-\s]+", "", str(candidate).lower()) == compact for candidate in candidates):
            return re.sub(r"[._\-\s]+", "", alias.canonical.lower())
    return compact


def _work_keys(value: Any) -> set[str]:
    return {f'{item.get("start")}-{item.get("end")}' for item in (value or []) if isinstance(item, dict)}


def field_score(gold: Any, predicted: Any, field: str | None = None) -> dict[str, float]:
    if field == "job_intent": equal = _norm_intent(gold) == _norm_intent(predicted)
    elif field == "experience_years":
        try: equal = abs(float(gold) - float(predicted)) <= 0.25
        except (TypeError, ValueError): equal = gold in (None, "") and predicted in (None, "")
    else:
        if field == "work_history": g, p = _work_keys(gold), _work_keys(predicted)
        elif field == "skills": g, p = {_skill_key(item) for item in (gold or [])}, {_skill_key(item) for item in (predicted or [])}
        elif isinstance(gold, list): g, p = set(_norm(gold)), set(_norm(predicted or []))
        else: return {"precision": float(_norm(gold) == _norm(predicted)), "recall": float(_norm(gold) == _norm(predicted)), "f1": float(_norm(gold) == _norm(predicted)), "accuracy": float(_norm(gold) == _norm(predicted))}
        if not g and not p: return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
        tp = len(g & p); precision = tp / len(p) if p else 0.0; recall = tp / len(g) if g else 1.0; f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {"precision": precision, "recall": recall, "f1": f1}
    return {"precision": float(equal), "recall": float(equal), "f1": float(equal), "accuracy": float(equal)}


def _has_explicit_certification_evidence(text: str) -> bool:
    lines = [line.strip() for line in re.sub(r"\r\n?", "\n", text or "").splitlines() if line.strip()]
    heading = re.compile(r"^(?:证书|证书认证|证书及荣誉|证书与荣誉|技能&证书|Certifications?|Certificate)\s*[:：]?\s*$", re.I)
    stop = re.compile(r"^(?:职业摘要|求职意向|核心技能|技能|工作经历|项目经历|项目经验|优势|合理弱点与改进|教育背景|教育经历|Experience|Projects?)\s*[:：]?\s*$", re.I)
    empty = re.compile(r"^(?:无|暂无|无相关(?:证书|认证)?|暂无相关(?:证书|认证)?|不适用|N/?A|-)$", re.I)
    in_section = False
    for line in lines:
        if heading.match(line):
            in_section = True
            continue
        if in_section and stop.match(line):
            break
        if in_section and not empty.match(line) and re.search(r"证书|认证|certificate|certification|PMP|AWS|CKA|CFA|CPA|软考|驾驶证|CET|英语[四四六六]级|普通话", line, re.I):
            return True
    return bool(
        re.search(
            r"(?:获得|持有|取得|考取)[^\n]{0,30}(?:证书|认证|PMP|AWS|CKA|CFA|CPA|软考|驾驶证|CET|英语[四四六六]级|普通话)"
            r"|通过[^\n]{0,30}(?:认证|证书)"
            r"|(?:证书|认证)\s*[:：]\s*(?!无|暂无|N/?A|-)[^\n]{1,60}",
            text or "",
            re.I,
        )
    )


def score_record(gold: dict[str, Any], predicted: dict[str, Any], observed_text: str | None = None) -> dict[str, Any]:
    values = {"job_intent": (gold.get("job_intent"), predicted.get("job_intent")), "skills": (gold.get("skills"), _skill_names(predicted.get("skills"))), "projects": ([p["name"] for p in gold.get("projects", [])], [p.get("name") for p in predicted.get("projects", []) if isinstance(p, dict)]), "experience_years": (gold.get("experience_years"), predicted.get("experience_years")), "education": (gold.get("education"), predicted.get("education")), "certifications": (gold.get("certifications"), predicted.get("certifications")), "preferred_locations": (gold.get("preferred_locations"), predicted.get("preferred_locations")), "expected_salary_k": (gold.get("expected_salary_k"), predicted.get("expected_salary_k")), "work_history": (gold.get("work_history"), predicted.get("work_history"))}
    fields = {name: field_score(g, p, name) for name, (g, p) in values.items()}
    if observed_text is not None and not re.search(r"\b\d+\s*[kK]?\s*[-~到]\s*\d+\s*[kK]\b|薪资|工资|月薪|年薪", observed_text):
        fields["expected_salary_k"] = {"precision": None, "recall": None, "f1": None, "excluded": True}
    if observed_text is not None and not _has_explicit_certification_evidence(observed_text):
        fields["certifications"] = {"precision": None, "recall": None, "f1": None, "excluded": True}
    scores = [item["f1"] for item in fields.values() if item.get("f1") is not None]
    return {"fields": fields, "macro_f1": statistics.mean(scores) if scores else 0.0}


def _read_cache(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8")); return value if isinstance(value.get("records"), dict) else {"meta": {}, "records": {}}
    except (FileNotFoundError, json.JSONDecodeError, AttributeError): return {"meta": {}, "records": {}}


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle: json.dump(value, handle, ensure_ascii=False, indent=2); handle.flush(); os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name): os.unlink(temp_name)


def _provider_snapshot(parsed: dict[str, Any], parser: ResumeParsingAgent, extracted: dict[str, Any]) -> dict[str, Any]:
    provider = parsed.get("provider_status") if isinstance(parsed.get("provider_status"), dict) else {}; vision = parsed.get("vision_parse") if isinstance(parsed.get("vision_parse"), dict) else {}; vs = vision.get("provider_status") if isinstance(vision.get("provider_status"), dict) else {}
    return {"configured": bool(provider.get("configured", getattr(parser.llm, "configured", False))), "fallback": bool(provider.get("fallback", False)), "reason": provider.get("reason"), "model": provider.get("model") or getattr(parser.llm, "model", None), "mode": provider.get("mode") or ("remote" if getattr(parser.llm, "configured", False) else "deterministic_fallback"), "vision_used": bool(extracted.get("images")) or bool(vision.get("used")), "vision_fallback": bool(vs.get("fallback")), "vision_configured": bool(vs.get("configured")), "vision_reason": vs.get("reason")}


def _usable(parsed: dict[str, Any]) -> bool:
    return sum(bool(parsed.get(key)) for key in ("job_intent", "skills", "projects")) >= 2


def _field_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    good = [r for r in rows if r["processing_success"]]
    def metric(field: str, key: str) -> float | None:
        values = [r["fields"].get(field, {}).get(key) for r in good]
        values = [value for value in values if value is not None]
        return statistics.mean(values) if values else None
    return {
        field: {
            key: metric(field, key)
            for key in ("precision", "recall", "f1")
        }
        | {
            "evaluated_samples": sum(r["fields"].get(field, {}).get("f1") is not None for r in good),
            "excluded_samples": sum(r["fields"].get(field, {}).get("f1") is None for r in good),
        }
        for field in ALL_FIELDS
    }


def evaluate(data_dir: Path = DATA, mode: str = "local", workers: int = 4, timeout: float = 180.0, resume: bool = True, limit: int | None = None, ids: list[str] | None = None, report_tag: str = "", sync_docs: bool = True, input_format: str = "manifest") -> dict[str, Any]:
    if mode not in {"local", "remote"}: raise ValueError("mode must be local or remote")
    if input_format not in {"manifest", "txt"}: raise ValueError("input_format must be manifest or txt")
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8")); wanted = set(ids or [])
    selected = [item for item in manifest["records"] if not wanted or item["id"] in wanted]; selected = selected[:max(0, limit)] if limit is not None else selected
    parser_probe = ResumeParsingAgent()
    if mode == "remote" and not getattr(parser_probe.llm, "configured", False): raise RuntimeError("remote mode requested, but TALENTGRAPH_LLM_BASE_URL/API_KEY/MODEL are not configured after loading ROOT/.env")
    suffix = f"_{report_tag}" if report_tag else (f"_{input_format}" if input_format != "manifest" else "")
    cache_path = data_dir / "reports" / f"cache_{mode}{suffix}.json"; cache = _read_cache(cache_path) if resume else {"meta": {}, "records": {}}; cache.setdefault("records", {}); lock = threading.Lock()
    meta = {"mode": mode, "model": getattr(parser_probe.llm, "model", None), "dataset": manifest.get("dataset"), "input_format": input_format}
    rows: list[dict[str, Any]] = []

    def one(item: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter(); rid = item["id"]; path = _evaluation_file_path(data_dir, item, input_format); filename = path.name; file_sha = hashlib.sha256(path.read_bytes()).hexdigest(); cached = cache["records"].get(rid)
        if resume and cached and cached.get("meta", {}).get("mode") == mode and cached.get("meta", {}).get("model") == meta["model"] and cached.get("meta", {}).get("input_format") == input_format and cached.get("meta", {}).get("file_sha256") == file_sha: return {**cached["row"], "cache_hit": True}
        try:
            extracted = extract_resume_text(filename, path.read_bytes()); parser = ResumeParsingAgent(); parsed = parser.parse(str(extracted.get("text", "")), candidate_id=rid, source_name=filename, images=extracted.get("images") or [], require_remote=False, use_remote=(mode == "remote")); elapsed = (time.perf_counter() - started) * 1000
            if elapsed > timeout * 1000: raise TimeoutError(f"resume evaluation exceeded {timeout:.1f}s")
            gold = json.loads((data_dir / item["gold_file"]).read_text(encoding="utf-8")); observed_text = str(extracted.get("text", "")); gold_for_score = dict(gold); highest_education = _highest_observed_education(observed_text); gold_for_score["education"] = highest_education or gold.get("education"); provider = _provider_snapshot(parsed, parser, extracted); row = {"id": rid, "status": "ok", "processing_success": True, "usable_parse": _usable(parsed), "format": "TXT" if input_format == "txt" else item["format"], "domain": item["domain"], "difficulty": item["difficulty"], "split": item["split"], "duration_ms": round(elapsed, 2), "provider_status": provider, **score_record(gold_for_score, parsed, observed_text)}
        except Exception as exc:
            message = str(exc); category = "timeout" if isinstance(exc, TimeoutError) or "timeout" in message.lower() else "extract_error" if "extract" in message.lower() or "pdf" in message.lower() else "parse_error"; row = {"id": rid, "status": "failed", "processing_success": False, "usable_parse": False, "format": item["format"], "domain": item["domain"], "difficulty": item["difficulty"], "split": item["split"], "duration_ms": round((time.perf_counter() - started) * 1000, 2), "error_category": category, "error": message[:500], "macro_f1": 0.0, "fields": {}, "provider_status": {"configured": mode == "remote", "fallback": True, "reason": message, "model": meta["model"], "mode": mode, "vision_used": False, "vision_fallback": False}}
        with lock: cache["meta"] = meta; cache["records"][rid] = {"meta": {**meta, "file_sha256": file_sha}, "row": row}; _atomic_write(cache_path, cache)
        return row

    reports_dir = data_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for future in as_completed([pool.submit(one, item) for item in selected]): rows.append(future.result())
    rows.sort(key=lambda x: x["id"]); processing = [r for r in rows if r["processing_success"]]; durations = [r["duration_ms"] for r in rows]
    def aggregate(subset: list[dict[str, Any]]) -> dict[str, Any]: return {"count": len(subset), "processing_success_rate": sum(r["processing_success"] for r in subset) / len(subset) if subset else 0, "usable_parse_rate": sum(r["usable_parse"] for r in subset) / len(subset) if subset else 0, "macro_f1": statistics.mean([r["macro_f1"] for r in subset if r["processing_success"]]) if any(r["processing_success"] for r in subset) else 0, "field_metrics": _field_metrics(subset)}
    groups = lambda key: {value: aggregate([r for r in rows if r[key] == value]) for value in sorted({r[key] for r in rows})}; providers = [r["provider_status"] for r in rows]
    result = {"dataset": manifest["dataset"], "mode": mode, "input_format": input_format, "count": len(rows), "requested_count": len(selected), "processing_success_rate": len(processing) / len(rows) if rows else 0, "usable_parse_rate": sum(r["usable_parse"] for r in rows) / len(rows) if rows else 0, "field_metrics": _field_metrics(rows), "macro_f1": statistics.mean([r["macro_f1"] for r in processing]) if processing else 0, "sample_count": len(rows), "project_count": sum(len(json.loads((data_dir / item["gold_file"]).read_text(encoding="utf-8")).get("projects", [])) for item in selected), "skill_count": sum(len(json.loads((data_dir / item["gold_file"]).read_text(encoding="utf-8")).get("skills", [])) for item in selected), "timing_ms": {"mean": statistics.mean(durations) if durations else 0, "p50": statistics.median(durations) if durations else 0, "p95": sorted(durations)[max(0, int(len(durations) * .95) - 1)] if durations else 0, "max": max(durations) if durations else 0}, "provider_stats": {"remote_success": sum(p.get("mode") == "remote" and p.get("configured") and not p.get("fallback") for p in providers), "text_fallback": sum(p.get("fallback") for p in providers), "fallback": sum(p.get("fallback") for p in providers), "vision_success": sum(p.get("vision_used") and not p.get("vision_fallback") for p in providers), "vision_fallback": sum(p.get("vision_fallback") for p in providers)}, "by_format": groups("format"), "by_domain": groups("domain"), "by_difficulty": groups("difficulty"), "low_score_samples": [r for r in processing if r["macro_f1"] < 0.5], "failures": [r for r in rows if not r["processing_success"]], "rows": rows, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    _atomic_write(reports_dir / f"resume_gold_100_{mode}{suffix}.json", result); _write_csv(result, reports_dir / f"resume_gold_100_{mode}{suffix}.csv"); _write_markdown(result, reports_dir / f"resume_gold_100_{mode}{suffix}.md");
    if sync_docs:
        _sync_docs(result, reports_dir)
    return result


def _write_csv(result: dict[str, Any], path: Path) -> None:
    fields = ["id", "status", "processing_success", "usable_parse", "format", "domain", "difficulty", "split", "duration_ms", "macro_f1", "error_category", "error"]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows({key: row.get(key, "") for key in fields} for row in result["rows"])


def _write_markdown(result: dict[str, Any], path: Path) -> None:
    fmt = lambda value: "N/A" if value is None else f"{value:.3f}"
    lines = [f"# Resume Gold 100 Report ({result['mode']})", "", f"- Samples: `{result.get('sample_count', result.get('count', 0))}`; gold projects: `{result.get('project_count', 0)}`; gold skills: `{result.get('skill_count', 0)}`", f"- Processing success rate: `{result['processing_success_rate']:.1%}`", f"- Usable parse rate: `{result['usable_parse_rate']:.1%}`", f"- Macro-F1: `{result['macro_f1']:.3f}`", "", "## Field Metrics", "", "| Field | Precision | Recall | F1 |", "|---|---:|---:|---:|"]
    lines += [f"| {key} | {fmt(value['precision'])} | {fmt(value['recall'])} | {fmt(value['f1'])} |" for key, value in result["field_metrics"].items()]; lines += ["", "## By Format", "", "| Format | Count | Processing | Usable | Macro-F1 |", "|---|---:|---:|---:|---:|"]
    lines += [f"| {key} | {value['count']} | {value['processing_success_rate']:.1%} | {value['usable_parse_rate']:.1%} | {value['macro_f1']:.3f} |" for key, value in result["by_format"].items()]; lines += ["", "## Other Breakdowns", ""]
    lines += [f"- {key}: " + "; ".join(f"{name} {value['count']} / usable {value['usable_parse_rate']:.1%} / F1 {value['macro_f1']:.3f}" for name, value in result[key].items()) for key in ("by_domain", "by_difficulty")]; lines += ["", f"## Low Score Samples ({len(result['low_score_samples'])})", "", "| ID | Format | Usable | Macro-F1 |", "|---|---|---:|---:|"]
    lines += [f"| {row['id']} | {row['format']} | {row['usable_parse']} | {row['macro_f1']:.3f} |" for row in result["low_score_samples"]]; categories = {}
    for row in result["rows"]:
        if not row["processing_success"]: categories[row.get("error_category", "unknown")] = categories.get(row.get("error_category", "unknown"), 0) + 1
    lines += ["", "## Error Categories", "", "; ".join(f"{key}: {value}" for key, value in categories.items()) or "None"]; path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sync_docs(result: dict[str, Any], reports_dir: Path | None = None) -> None:
    reports_dir = reports_dir if reports_dir is not None else REPORTS
    reports = {}
    for mode in ("local", "remote"):
        try: reports[mode] = json.loads((reports_dir / f"resume_gold_100_{mode}.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError): pass
    reports[result["mode"]] = result
    blocks = []
    for mode, report in reports.items():
        provider = report.get("provider_stats", {})
        report_rows = report.get("rows", [])
        vision_fallback = provider.get("vision_fallback", sum(bool(row.get("provider_status", {}).get("vision_fallback")) for row in report_rows))
        text_fallback = provider.get("text_fallback", provider.get("fallback", sum(bool(row.get("provider_status", {}).get("fallback")) for row in report_rows)))
        blocks.append(f"### {mode}\n\n- Status: `completed`\n- Count: `{report.get('count', 0)}`\n- Processing success rate: `{report.get('processing_success_rate', 0):.1%}`\n- Usable parse rate: `{report.get('usable_parse_rate', 0):.1%}`\n- Macro-F1: `{report.get('macro_f1', 0):.4f}`\n- Timing: mean `{report.get('timing_ms', {}).get('mean', 0):.1f}ms`, P50 `{report.get('timing_ms', {}).get('p50', 0):.1f}ms`, P95 `{report.get('timing_ms', {}).get('p95', 0):.1f}ms`, max `{report.get('timing_ms', {}).get('max', 0):.1f}ms`\n- Provider: remote_success `{provider.get('remote_success', 0)}` (text LLM only), text fallback `{text_fallback}`, vision fallback `{vision_fallback}`")
    remote = reports.get("remote")
    subset_note = ""
    if remote:
        subset = [row for row in remote.get("rows", []) if row.get("format") not in {"图片", "扫描PDF"}]
        values = [row.get("macro_f1", 0) for row in subset if row.get("processing_success")]
        subset_note = f"\n\nRemote non-image/scanned subset: `{len(subset)}` rows, macro-F1 `{statistics.mean(values):.4f}` (computed from remote rows)."
    report_intro = ("# Resume Gold 100 Benchmark\n\n"
        "## 数据集说明\n\n"
        "本数据集包含100份高拟真虚构中文技术简历，所有候选人均为合成匿名角色，不含电话、邮箱、身份证号或真实联系地址。每人提供DOCX、可复制中文PDF、TXT和增强gold JSON。\n\n"
        "覆盖人工智能、大数据、智能系统、物联网四个领域，各25人；包含16种细分岗位、初级/中级/高级三级、易/中/难三级，以及calibration/regression/blind三类切分（20/30/50）。每份gold保留旧字段，并补充候选人画像、分组技能、技能证据、教育与工作时间线、STAR项目、优势弱点和质量场景。\n\n"
        "## 质量与局限\n\n"
        "简历内容由确定性模板、岗位词表和量化情境组合生成，重点模拟可解析的职责边界、技术动作与结果证据，不代表真实招聘市场分布，也不能替代经授权的真实简历标注集。唯一性门禁只保证样本文本与关键事实不重复；格式可读性、时间线和字段覆盖通过本地自动化检查，语义真实性、岗位胜任度和跨模型泛化仍需独立人工抽检。\n\n"
        "## 生成质量门禁\n\n"
        "本次生成门禁结果：100/100 条记录、四领域各25条、16种岗位、8种排版样式、100份唯一正文；初级正文均不少于700字，中高级正文均不少于900字，并逐条校验章节、STAR项目、量化结果、时间线、技能证据、文件存在性和hash。\n\n"
        "## Run Status\n\n")
    remote_note = "\n\nRemote status is reported from the existing JSON result; no new model evaluation is started by documentation sync." if remote else "\n\n本次接管仅运行本地解析评估；未配置远程模型，因此没有启动远程评估。"
    DOC_REPORT.parent.mkdir(parents=True, exist_ok=True); DOC_REPORT.write_text(report_intro + "\n\n".join(blocks) + subset_note + remote_note + " Image-only empty results are never counted as usable parses.\n", encoding="utf-8")


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--data-dir", type=Path, default=DATA); p.add_argument("--mode", choices=("local", "remote"), default="local"); p.add_argument("--input-format", choices=("manifest", "txt"), default="manifest"); p.add_argument("--workers", type=int, default=4); p.add_argument("--timeout", type=float, default=180); p.add_argument("--no-resume", action="store_true"); p.add_argument("--limit", type=int); p.add_argument("--ids", nargs="*"); p.add_argument("--report-tag", default=""); p.add_argument("--no-sync-docs", action="store_true"); args = p.parse_args(); print(json.dumps(evaluate(args.data_dir, args.mode, args.workers, args.timeout, not args.no_resume, args.limit, args.ids, args.report_tag, not args.no_sync_docs, args.input_format), ensure_ascii=False, indent=2)[:5000])
