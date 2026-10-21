from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from scripts.generate_resume_gold_100 import DOMAINS, generate
import scripts.evaluate_resume_gold_100 as evaluator
from scripts.evaluate_resume_gold_100 import _evaluation_file_path, _has_explicit_certification_evidence, _highest_observed_education, field_score, score_record


def _months(value: str) -> int:
    year, month = (int(part) for part in value.split("."))
    return year * 12 + month


def _read_gold(root: Path, item: dict) -> dict:
    return json.loads((root / item["gold_file"]).read_text(encoding="utf-8"))


def test_generated_distribution_and_quality_gate(tmp_path: Path):
    manifest = generate(tmp_path)
    records = manifest["records"]
    assert manifest["count"] == 100
    assert manifest["quality_gate"]["passed"] is True
    assert {domain: sum(item["domain"] == domain for item in records) for domain in DOMAINS} == {domain: 25 for domain in DOMAINS}
    assert len({item["role"] for item in records}) >= 12
    assert {level: sum(item["level"] == level for item in records) for level in ("初级", "中级", "高级")} == {"初级": 25, "中级": 30, "高级": 45}
    assert {split: sum(item["split"] == split for item in records) for split in ("calibration", "regression", "blind")} == {"calibration": 20, "regression": 30, "blind": 50}
    assert len(set(item["layout_style"] for item in records)) >= 6
    assert all(item["available_formats"] == ["DOCX", "可复制中文PDF", "TXT"] for item in records)


def test_generation_is_reproducible(tmp_path: Path):
    first = generate(tmp_path / "a")
    second = generate(tmp_path / "b")
    assert [(item["id"], item["file_hashes"]) for item in first["records"]] == [(item["id"], item["file_hashes"]) for item in second["records"]]


def test_quality_fields_timeline_and_artifacts(tmp_path: Path):
    manifest = generate(tmp_path)
    normalized_texts = []
    required_sections = ("职业摘要", "求职意向", "教育背景", "核心技能", "工作经历", "项目经历", "优势", "合理弱点与改进")
    for item in manifest["records"]:
        gold = _read_gold(tmp_path, item)
        text = (tmp_path / item["file_paths"]["txt"]).read_text(encoding="utf-8")
        normalized_texts.append(re.sub(r"\s+", "", text))
        assert len(text.replace("\n", "")) >= (700 if item["level"] == "初级" else 900)
        assert all(section in text for section in required_sections)
        assert all(key in gold for key in ("candidate_profile", "summary", "skills_grouped", "skill_evidence", "education_detail", "work_history", "projects", "strengths", "weaknesses", "role_family", "quality_scenario"))
        assert gold["candidate_profile"]["fictional"] is True
        assert not re.search(r"\b1[3-9]\d{9}\b|\b1\d{10}\b|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
        assert 2 <= len(gold["projects"]) <= 3
        assert len(gold["skill_evidence"]) >= sum(len(values) for values in gold["skills_grouped"].values())
        for project in gold["projects"]:
            assert all(project.get(key) for key in ("background", "responsibility_boundary", "technical_actions", "quantified_results"))
            assert any(re.search(r"\d", result) for result in project["quantified_results"])
        work = gold["work_history"]
        assert work == sorted(work, key=lambda entry: entry["start"])
        assert all(_months(work[pos]["end"]) <= _months(work[pos + 1]["start"]) for pos in range(len(work) - 1))
        for artifact in item["artifacts"].values():
            path = tmp_path / artifact["path"]
            assert path.exists() and path.read_bytes()
            assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
    assert len(set(normalized_texts)) == 100


def test_sample_files_are_readable_and_pdf_text_is_copyable(tmp_path: Path):
    manifest = generate(tmp_path)
    sample_ids = {"resume_001", "resume_025", "resume_050", "resume_075", "resume_100"}
    for item in manifest["records"]:
        if item["id"] not in sample_ids:
            continue
        gold = _read_gold(tmp_path, item)
        expected_name = gold["candidate_profile"]["name"]
        pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(tmp_path / item["file_paths"]["pdf"]).pages)
        docx_text = "\n".join(paragraph.text for paragraph in Document(tmp_path / item["file_paths"]["docx"]).paragraphs)
        txt_text = (tmp_path / item["file_paths"]["txt"]).read_text(encoding="utf-8")
        assert expected_name in pdf_text and "项目经历" in pdf_text and len(pdf_text) > 700
        assert expected_name in docx_text and "项目经历" in docx_text and len(docx_text) > 700
        assert expected_name in txt_text and "项目经历" in txt_text


def test_scoring_functions():
    assert field_score(["Python", "SQL"], ["Python"]) == {"precision": 1.0, "recall": 0.5, "f1": 2 / 3}
    gold = {"job_intent": "AI 应用工程师", "skills": ["Python"], "projects": [{"name": "知识平台"}], "experience_years": 2, "education": "本科", "certifications": [], "preferred_locations": ["北京"], "expected_salary_k": [10, 20], "work_history": [{"start": "2022.03", "end": "2023.06"}]}
    parsed = {"job_intent": "AI 应用工程师", "skills": [{"name": "Python"}], "projects": [{"name": "知识平台"}], "experience_years": 2, "education": "本科", "certifications": [], "preferred_locations": ["北京"], "expected_salary_k": [10, 20], "work_history": [{"start": "2022.03", "end": "2023.06"}]}
    assert score_record(gold, parsed)["macro_f1"] == 1.0


def test_highest_observed_education_uses_education_section_only():
    text = "教育经历\n本科\n硕士\n工作经历\n博士要求不代表候选人学历"

    assert _highest_observed_education(text) == "硕士"


def test_evaluation_file_path_can_select_txt_artifact():
    item = {
        "filename": "resume_001.pdf",
        "file_paths": {"txt": "files/resume_001.txt"},
    }

    assert _evaluation_file_path(Path("/dataset"), item, "txt") == Path("/dataset/files/resume_001.txt")


def test_scoring_uses_intent_prefix_and_experience_tolerance():
    assert field_score("求职意向：AI 应用工程师", "AI  应用工程师", "job_intent")["f1"] == 1.0
    assert field_score(3.0, 3.24, "experience_years")["f1"] == 1.0
    assert field_score(3.0, 3.26, "experience_years")["f1"] == 0.0
    assert field_score([{"start": "2022.01", "end": "2023.01"}], [{"start": "2022.01", "end": "2023.01", "company": "extra"}], "work_history")["f1"] == 1.0


def test_salary_and_empty_certification_are_excluded_from_denominator():
    gold = {"expected_salary_k": [], "certifications": []}
    parsed = {"expected_salary_k": [], "certifications": []}
    result = score_record(gold, parsed, "核心技能\nPython\n证书\n暂无")

    assert result["fields"]["expected_salary_k"]["f1"] is None
    assert result["fields"]["certifications"]["f1"] is None
    assert not _has_explicit_certification_evidence("证书\n暂无")
    assert _has_explicit_certification_evidence("证书\nPMP")
    assert not _has_explicit_certification_evidence("工作经历\n通过上线验证")


def test_usable_parse_requires_two_primary_fields():
    assert evaluator._usable({"job_intent": "工程师", "skills": ["Python"], "projects": []})
    assert not evaluator._usable({"job_intent": None, "skills": [], "projects": []})
    assert not evaluator._usable({"job_intent": None, "skills": ["Python"], "projects": []})


def test_checkpoint_has_metadata_and_supports_limit(tmp_path: Path, monkeypatch):
    manifest = generate(tmp_path)
    monkeypatch.setattr(evaluator, "DOC_REPORT", tmp_path / "synced.md")
    result = evaluator.evaluate(tmp_path, mode="local", workers=1, limit=2, resume=False)
    assert result["requested_count"] == 2
    for suffix in ("json", "csv", "md"):
        assert (tmp_path / f"reports/resume_gold_100_local.{suffix}").is_file()
    checkpoint = json.loads((tmp_path / "reports/cache_local.json").read_text(encoding="utf-8"))
    assert checkpoint["meta"]["mode"] == "local"
    assert len(checkpoint["records"]) == 2
    assert all("file_sha256" in entry["meta"] and "model" in entry["meta"] for entry in checkpoint["records"].values())
    resumed = evaluator.evaluate(tmp_path, mode="local", workers=1, ids=[manifest["records"][0]["id"]], resume=True)
    assert resumed["rows"][0]["cache_hit"] is True
    assert (tmp_path / "synced.md").exists()


def test_remote_without_model_configuration_fails_fast(tmp_path: Path, monkeypatch):
    generate(tmp_path)
    for key in ("TALENTGRAPH_LLM_BASE_URL", "TALENTGRAPH_LLM_API_KEY", "TALENTGRAPH_LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(evaluator, "DOC_REPORT", tmp_path / "synced.md")
    try:
        evaluator.evaluate(tmp_path, mode="remote", limit=1)
    except RuntimeError as exc:
        assert "remote mode requested" in str(exc)
    else:
        raise AssertionError("remote mode must not silently fall back to local")


def test_provider_stats_and_docs_sync_read_existing_reports(tmp_path: Path, monkeypatch):
    reports = tmp_path / "reports"
    reports.mkdir()
    remote = {"mode": "remote", "count": 100, "macro_f1": 0.774597, "processing_success_rate": 1.0, "usable_parse_rate": 0.8, "timing_ms": {}, "provider_stats": {"remote_success": 0, "text_fallback": 90}, "rows": [{"format": "普通PDF", "macro_f1": 0.95, "processing_success": True, "provider_status": {"fallback": True, "vision_fallback": False}}] * 90 + [{"format": "扫描PDF", "macro_f1": 0.0, "processing_success": True, "provider_status": {"fallback": True, "vision_fallback": True}}] * 10 + [{"format": "图片", "macro_f1": 0.0, "processing_success": True, "provider_status": {"fallback": False, "vision_fallback": True}}] * 10}
    (reports / "resume_gold_100_remote.json").write_text(json.dumps(remote), encoding="utf-8")
    monkeypatch.setattr(evaluator, "REPORTS", reports)
    docs = tmp_path / "report.md"
    monkeypatch.setattr(evaluator, "DOC_REPORT", docs)
    evaluator._sync_docs(remote)
    content = docs.read_text(encoding="utf-8")
    assert "remote_success `0` (text LLM only)" in content
    assert "text fallback `90`" in content
    assert "vision fallback `20`" in content
    assert "macro-F1 `0.9500`" in content
    assert content.count("### remote") == 1
