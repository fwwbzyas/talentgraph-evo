from __future__ import annotations

import json
import argparse
import statistics
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.assessment.resume_files import extract_resume_text
from agents.assessment.resume_parser import ResumeParsingAgent
from scripts.evaluate_resume_gold_100 import ALL_FIELDS, field_score, score_record


# Independent human gold: only facts visibly stated in each extracted resume.


def main() -> None:
    cli = argparse.ArgumentParser(description="Evaluate locally supplied, authorized resume data.")
    cli.add_argument("--resume-dir", type=Path, default=ROOT / "data/private/real_resumes")
    cli.add_argument("--gold-file", type=Path, default=ROOT / "data/private/real_resumes/gold.json")
    cli.add_argument("--output-dir", type=Path, default=ROOT / "data/evaluation/real_resumes")
    args = cli.parse_args()
    REAL, gold_file, OUT = [(p.expanduser() if p.expanduser().is_absolute() else ROOT / p.expanduser()).resolve()
                            for p in (args.resume_dir, args.gold_file, args.output_dir)]
    if not gold_file.is_file():
        cli.error(f"Gold labels not found: {gold_file}; supply --gold-file (JSON mapping filenames to labels).")
    GOLD = json.loads(gold_file.read_text(encoding="utf-8"))
    if not isinstance(GOLD, dict) or not GOLD:
        cli.error("Gold labels must be a non-empty JSON object mapping filenames to labels.")
    for filename in GOLD:
        path = (REAL / filename).resolve()
        if not path.is_relative_to(REAL) or not path.is_file():
            cli.error(f"Resume file missing or outside --resume-dir: {filename}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "real_resume_15_gold.json").write_text(json.dumps(GOLD, ensure_ascii=False, indent=2), encoding="utf-8")
    parser = ResumeParsingAgent()
    rows = []
    for filename, gold in GOLD.items():
        path = REAL / filename
        extracted = extract_resume_text(filename, path.read_bytes())
        text = str(extracted.get("text", ""))
        parsed = parser.parse(text, source_name=filename, use_remote=False)
        score_gold = {**gold, "projects": [{"name": name} for name in gold["projects"]], "certifications": gold.get("certifications", []), "expected_salary_k": gold.get("expected_salary_k", [])}
        scored = score_record(score_gold, parsed, text)
        errors = [field for field in ALL_FIELDS if scored["fields"].get(field, {}).get("f1") == 0]
        error_examples = [{"field": field, "gold": score_gold.get(field), "predicted": parsed.get(field), "reason": "parser missed explicit evidence or emitted a non-matching value"} for field in errors]
        rows.append({"filename": filename, "format": path.suffix.lower().lstrip("."), "extraction": {"ok": bool(text.strip()), "chars": len(text), "images": len(extracted.get("images") or [])}, "gold": gold, "predicted": parsed, "fields": scored["fields"], "macro_f1": scored["macro_f1"], "errors": errors, "error_examples": error_examples})
    valid = [row for row in rows if row["extraction"]["ok"]]
    metrics = {}
    for field in ALL_FIELDS:
        values = [row["fields"].get(field, {}).get(key) for row in valid for key in ("precision", "recall", "f1")]
        metrics[field] = {key: (statistics.mean([row["fields"].get(field, {}).get(key) for row in valid if row["fields"].get(field, {}).get(key) is not None]) if any(row["fields"].get(field, {}).get(key) is not None for row in valid) else None) for key in ("precision", "recall", "f1")}
    result = {"sample_count": len(rows), "extraction_success_count": sum(row["extraction"]["ok"] for row in rows), "gold_project_count": sum(len(row["gold"]["projects"]) for row in rows), "gold_skill_count": sum(len(row["gold"]["skills"]) for row in rows), "macro_f1": statistics.mean(row["macro_f1"] for row in valid), "field_metrics": metrics, "failures": [row["filename"] for row in rows if not row["extraction"]["ok"]], "rows": rows}
    (OUT / "real_resume_15_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Real Resume 15 Evaluation", "", f"- Samples: `{result['sample_count']}`", f"- Extraction success: `{result['extraction_success_count']}/{result['sample_count']}`", f"- Gold projects: `{result['gold_project_count']}`", f"- Gold skills: `{result['gold_skill_count']}`", f"- Overall Macro-F1: `{result['macro_f1']:.4f}`", "", "| Field | Precision | Recall | F1 |", "|---|---:|---:|---:|"]
    for field, metric in metrics.items():
        fmt = lambda value: "N/A" if value is None else f"{value:.4f}"
        lines.append(f"| {field} | {fmt(metric['precision'])} | {fmt(metric['recall'])} | {fmt(metric['f1'])} |")
    lines += ["", "## Per-sample", "", "| File | Format | Chars | Macro-F1 | Errors |", "|---|---|---:|---:|---|"]
    lines += [f"| {row['filename']} | {row['format']} | {row['extraction']['chars']} | {row['macro_f1']:.4f} | {', '.join(row['errors']) or 'None'} |" for row in rows]
    lines += ["", "## Method", "", "Gold was manually established from each extracted original text before parsing. Only explicitly visible fields were labeled; salary and certification are N/A unless explicitly marked. Skills use normalized aliases; no parser output was used to create gold.", "", "## Error Examples", ""]
    lines += [f"### {row['filename']}\n" + ("\n".join(f"- `{error['field']}`: gold={error['gold']!r}; predicted={error['predicted']!r}; reason={error['reason']}" for error in row["error_examples"]) or "- None") for row in rows]
    lines += ["", "## Failures", "", ", ".join(result["failures"]) or "None"]
    (OUT / "real_resume_15_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("sample_count", "extraction_success_count", "gold_project_count", "gold_skill_count", "macro_f1", "field_metrics", "failures")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
