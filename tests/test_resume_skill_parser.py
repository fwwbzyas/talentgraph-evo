from agents.assessment.resume_parser import ResumeParsingAgent


def _names(text: str):
    return [item["name"] for item in ResumeParsingAgent().parse(text, use_remote=False)["skills"]]


def test_skill_extraction_stops_before_skill_evidence_heading():
    names = _names(
        """
        核心技能
        编程语言：Python、SQL、Git
        服务与工程：FastAPI、Docker
        技能证据
        Python（编程语言）：在项目中负责接口开发，最终延迟下降20%。
        技能证据句不应成为技能
        项目经历
        项目1｜知识平台｜核心开发
        """
    )

    assert set(names) == {"Python", "SQL", "Git", "FastAPI", "Docker"}
    assert "技能证据句不应成为技能" not in names


def test_grouped_skill_line_uses_only_colon_right_hand_side():
    names = _names(
        """
        核心技能
        编程语言：Python、SQL、Git
        模型与算法：Prompt工程
        """
    )

    assert set(names) == {"Python", "SQL", "Git", "Prompt Engineering"}
    assert "编程语言" not in names
    assert all("：" not in name and ":" not in name for name in names)


def test_skill_tokens_reject_evidence_sentences_and_metrics():
    names = _names(
        """
        技能
        Python、SQL
        负责接口开发，延迟下降20%
        命中率提升15%
        """
    )

    assert set(names) == {"Python", "SQL"}


def test_skill_alias_boundaries_keep_c_distinct_from_cpp():
    names = _names("核心技能\n语言：C++、Python\n技能证据\nC++开发")

    assert "C++" in names
    assert "C" not in names


def test_prompt_aliases_are_deduplicated_and_project_only_skills_are_supplemental():
    parser = ResumeParsingAgent()
    result = parser.parse(
        """
        核心技能
        模型与算法：Prompt工程
        技能证据
        Prompt Engineering：在项目中使用提示词工程完成验证。
        项目经历
        项目1｜知识平台｜核心开发
        技术动作：使用Redis完成缓存建设。
        """,
        use_remote=False,
    )

    names = [item["name"] for item in result["skills"]]
    assert names.count("Prompt Engineering") == 1
    assert "Redis" not in names
    assert [item["name"] for item in result["supplemental_skills"]] == ["Redis"]


def test_remote_skill_merge_keeps_project_only_skills_supplemental():
    parser = ResumeParsingAgent()
    text = """
    核心技能
    编程语言：Python
    项目经历
    项目1｜知识问答平台｜2024.01-2024.06｜开发
    技术动作：使用 Redis 完成缓存建设，延迟下降20%。
    """
    fallback = parser._deterministic_parse(text, candidate_id=None, source_name="test")

    merged = parser._merge_llm_result(
        fallback,
        {"skills": [{"name": "Redis", "evidence": "使用 Redis 完成缓存建设"}]},
        text,
    )

    assert "Redis" not in [item["name"] for item in merged["skills"]]
    assert "Redis" in [item["name"] for item in merged["supplemental_skills"]]


def test_compound_skill_tokens_are_not_split_or_shadowed():
    names = _names(
        """
        核心技能
        分析方法：A/B测试
        质量与协作：CI/CD
        边缘与模型：ONNX Runtime
        """
    )

    assert "A/B测试" in names
    assert "CI/CD" in names
    assert "ONNX Runtime" in names
    assert "ONNX" not in names
