from __future__ import annotations

import csv
import json
import argparse
import re
import statistics
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "data/evaluation/resume_gold_100"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.assessment.resume_files import extract_resume_text
from agents.assessment.resume_parser import ResumeParsingAgent
from scripts.evaluate_resume_gold_100 import ALL_FIELDS, _highest_observed_education, field_score


ALIASES = {
    "cpp": "c++", "c＋＋": "c++", "c++": "c++", "pytorch": "pytorch", "torch": "pytorch",
    "prompt工程": "prompt engineering", "提示词工程": "prompt engineering", "prompt engineering": "prompt engineering",
    "javascript": "javascript", "js": "javascript", "typescript": "typescript", "ts": "typescript",
    "ros2": "ros 2", "ros 2": "ros 2", "nodejs": "node.js", "node.js": "node.js",
    "大学英语四级": "cet-4", "大学英语六级": "cet-6", "cet4": "cet-4", "cet-4": "cet-4", "cet6": "cet-6", "cet-6": "cet-6",
}


def _norm_token(value: object) -> str:
    raw = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    compact = re.sub(r"[\s._/－-]+", "", raw)
    return ALIASES.get(raw, ALIASES.get(compact, raw))


def _norm_list(values: object) -> list[str]:
    return sorted({_norm_token(value) for value in (values or []) if value not in (None, "", [])})


def _norm_project(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("name", "")
    text = re.sub(r"\s+", " ", str(value or "")).strip(" ：:;-，,。")
    text = re.sub(r"^\s*[（(]?[一二三四五六七八九十\d]+[）)]\s*", "", text)
    text = re.sub(r"^(?:19|20)\d{2}[./年]\d{1,2}\W+(?:19|20)\d{2}[./年]\d{1,2}\s*", "", text)
    text = re.sub(r"\s+(?:项目负责人|核心开发者|开发工程师|前端负责人|后端开发|全栈独立开发|独立开发|项目经理|项目成员)\s*$", "", text)
    return text.lower().strip(" ：:;-，,。")


def _work_keys(values: object) -> list[str]:
    return sorted({(f"{item.get('start')}-{item.get('end')}" if isinstance(item, dict) else str(item)) for item in (values or []) if isinstance(item, dict) or item})


def _score(gold: dict, predicted: dict, text: str) -> dict:
    gold = {**gold, "skills": _norm_list(gold.get("skills")), "projects": [_norm_project(x) for x in gold.get("projects", [])], "preferred_locations": _norm_list(gold.get("preferred_locations")), "certifications": _norm_list(gold.get("certifications"))}
    predicted = {**predicted, "skills": _norm_list([x.get("name") if isinstance(x, dict) else x for x in predicted.get("skills", [])]), "projects": [_norm_project(x.get("name") if isinstance(x, dict) else x) for x in predicted.get("projects", [])], "preferred_locations": _norm_list(predicted.get("preferred_locations")), "certifications": _norm_list(predicted.get("certifications"))}
    fields = {}
    for field in ALL_FIELDS:
        if field == "work_history":
            fields[field] = field_score(gold.get(field), predicted.get(field), field)
        else:
            fields[field] = field_score(gold.get(field), predicted.get(field), field)
    if not re.search(r"\b\d+\s*[kK]?\s*[-~到]\s*\d+\s*[kK]\b|薪资|工资|月薪|年薪", text):
        fields["expected_salary_k"] = {"precision": None, "recall": None, "f1": None, "excluded": True}
    if not re.search(r"证书|认证|certificate|certification", text, re.I):
        fields["certifications"] = {"precision": None, "recall": None, "f1": None, "excluded": True}
    scores = [item["f1"] for item in fields.values() if item.get("f1") is not None]
    return {"fields": fields, "macro_f1": statistics.mean(scores) if scores else 0.0}


def _load_real_gold(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    cli = argparse.ArgumentParser(description="Evaluate synthetic and locally supplied resume data.")
    cli.add_argument("--resume-dir", type=Path, default=ROOT / "data/private/real_resumes")
    cli.add_argument("--gold-file", type=Path, default=ROOT / "data/private/real_resumes/gold.json")
    cli.add_argument("--synthetic-dir", type=Path, default=SYNTHETIC)
    cli.add_argument("--output-dir", type=Path, default=ROOT / "data/evaluation/real_resumes")
    args = cli.parse_args()
    REAL, gold_file, synthetic_dir, OUT = [(p.expanduser() if p.expanduser().is_absolute() else ROOT / p.expanduser()).resolve()
                                         for p in (args.resume_dir, args.gold_file, args.synthetic_dir, args.output_dir)]
    if not gold_file.is_file():
        cli.error(f"Gold labels not found: {gold_file}; supply --gold-file.")
    if not (synthetic_dir / "manifest.json").is_file():
        cli.error(f"Synthetic manifest not found: {synthetic_dir / 'manifest.json'}; generate the dataset first.")
    parser = ResumeParsingAgent()
    real_gold = _load_real_gold(gold_file)
    if not isinstance(real_gold, dict) or not real_gold:
        cli.error("Gold labels must be a non-empty JSON object.")
    for filename in real_gold:
        path = (REAL / filename).resolve()
        if not path.is_relative_to(REAL) or not path.is_file():
            cli.error(f"Resume file missing or outside --resume-dir: {filename}")
    rows = []
    manifest = json.loads((synthetic_dir / "manifest.json").read_text(encoding="utf-8"))
    selected = sorted(manifest["records"], key=lambda item: item["id"])[:85]
    assignments = ["DOCX"] * 29 + ["PDF"] * 28 + ["TXT"] * 28
    for item, format_name in zip(selected, assignments):
        filename = item["file_paths"][format_name.lower()].split("/")[-1]
        path = synthetic_dir / item["file_paths"][format_name.lower()]
        extracted = extract_resume_text(filename, path.read_bytes()); text = str(extracted.get("text", "")); parsed = parser.parse(text, source_name=filename, use_remote=False)
        gold = json.loads((synthetic_dir / item["gold_file"]).read_text(encoding="utf-8")); gold = {**gold, "education": _highest_observed_education(text) or gold.get("education")}
        scored = _score(gold, parsed, text); rows.append({"group": "synthetic85", "id": item["id"], "filename": filename, "format": format_name, "extraction_ok": bool(text.strip()), "gold": gold, "predicted": parsed, **scored, "errors": [field for field in ALL_FIELDS if scored["fields"].get(field, {}).get("f1") == 0]})
    for filename, gold in sorted(real_gold.items()):
        path = REAL / filename; extracted = extract_resume_text(filename, path.read_bytes()); text = str(extracted.get("text", "")); parsed = parser.parse(text, source_name=filename, use_remote=False); scored = _score(gold, parsed, text)
        rows.append({"group": "real15", "id": filename, "filename": filename, "format": path.suffix.lower().lstrip("."), "extraction_ok": bool(text.strip()), "gold": gold, "predicted": parsed, **scored, "errors": [field for field in ALL_FIELDS if scored["fields"].get(field, {}).get("f1") == 0]})
    def aggregate(subset: list[dict]) -> dict:
        metrics = {}
        for field in ALL_FIELDS:
            metrics[field] = {key: (statistics.mean([row["fields"].get(field, {}).get(key) for row in subset if row["fields"].get(field, {}).get(key) is not None]) if any(row["fields"].get(field, {}).get(key) is not None for row in subset) else None) for key in ("precision", "recall", "f1")}
        return {"sample_count": len(subset), "extraction_success_count": sum(row["extraction_ok"] for row in subset), "macro_f1": statistics.mean(row["macro_f1"] for row in subset), "field_metrics": metrics, "failures": [row["filename"] for row in subset if not row["extraction_ok"]], "format_counts": {fmt: sum(row["format"] == fmt for row in subset) for fmt in sorted({row["format"] for row in subset})}}
    groups = {name: aggregate([row for row in rows if row["group"] == name]) for name in ("synthetic85", "real15")}; groups["combined100"] = aggregate(rows)
    result = {"method": "synthetic85 unique records with fixed 29 DOCX/28 PDF/28 TXT assignment plus independently human-labeled real15; use_remote=False", "groups": groups, "rows": rows}
    OUT.mkdir(parents=True, exist_ok=True); (OUT / "combined_100_after_optimization.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["group", "id", "filename", "format", "macro_f1", *[f"{field}_f1" for field in ALL_FIELDS], "errors"]
    with (OUT / "combined_100_after_optimization.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows({"group": row["group"], "id": row["id"], "filename": row["filename"], "format": row["format"], "macro_f1": row["macro_f1"], **{f"{field}_f1": row["fields"].get(field, {}).get("f1") for field in ALL_FIELDS}, "errors": ",".join(row["errors"])} for row in rows)
    lines = ["# Combined Resume Evaluation (85 Synthetic + 15 Real)", "", result["method"], "", "## Group Metrics", ""]
    for name, group in groups.items():
        lines += [f"### {name}", "", f"- Samples: `{group['sample_count']}`; extraction: `{group['extraction_success_count']}`; Macro-F1: `{group['macro_f1']:.4f}`", "", "| Field | Precision | Recall | F1 |", "|---|---:|---:|---:|"]
        for field, metric in group["field_metrics"].items():
            fmt = lambda value: "N/A" if value is None else f"{value:.4f}"
            lines.append(f"| {field} | {fmt(metric['precision'])} | {fmt(metric['recall'])} | {fmt(metric['f1'])} |")
        lines.append("")
    lines += ["## Per-sample Errors", ""]
    lines += [f"- `{row['group']}` `{row['filename']}`: {', '.join(row['errors']) or 'None'}" for row in rows]
    (OUT / "combined_100_after_optimization.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(groups, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
