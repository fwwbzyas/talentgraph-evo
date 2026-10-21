from agents.match.service import MatchAgent
from contracts import CandidateProfile, JobGraph, SkillRequirement


def test_match_report_is_built_from_profile_and_job_graph():
    graph = JobGraph(
        job_id="job_ai_agent",
        job_title="AI Agent 工程师",
        domain="人工智能",
        responsibilities=["建设企业智能体平台"],
        skills=[
            SkillRequirement(
                skill_id="skill_python",
                name="Python",
                category="language",
                required_level="intermediate",
                importance="required",
                confidence=0.9,
            ),
            SkillRequirement(
                skill_id="skill_rag",
                name="RAG",
                category="ai_engineering",
                required_level="advanced",
                importance="required",
                confidence=0.9,
            ),
            SkillRequirement(
                skill_id="skill_k8s",
                name="Kubernetes",
                category="devops",
                required_level="intermediate",
                importance="preferred",
                confidence=0.8,
            ),
        ],
        scenarios=["企业知识库问答质量突然下降"],
    )
    profile = CandidateProfile(
        candidate_id="candidate_1",
        target_job_id="job_ai_agent",
        skills=[
            {
                "name": "Python",
                "level": "advanced",
                "evidence": "使用 Python 完成 RAG 评测脚本",
                "confidence": 0.9,
            }
        ],
        projects=[{"name": "知识库平台", "evidence": "使用 Python 完成 RAG 评测脚本"}],
        evidence=[{"content": "使用 Python 完成 RAG 评测脚本"}],
        confidence=0.82,
        competency_dimensions=[{"name": "问题解决", "score": 82}],
    )

    report = MatchAgent().run(graph, profile)

    assert report.matched_skills == ["Python"]
    assert report.missing_required_skills == ["RAG"]
    assert report.strengths[0]["skill"] == "Python"
    assert any(gap["skill"] == "RAG" for gap in report.gaps)
    assert any("RAG" in question for question in report.follow_up_questions)
    assert report.job_snapshot["matched_skill_count"] == 1
    assert report.job_snapshot["evidence_summary"]["profile_evidence_count"] == 1
