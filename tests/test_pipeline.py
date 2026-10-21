from contracts import AssessmentAnswer, GameResultInput, ImportRequest, JobGraphBuildRequest
from core.orchestrator import Orchestrator
from core.sample_data import generate_demo_jds


def run_demo_pipeline():
    orchestrator = Orchestrator()
    batch = orchestrator.import_data(ImportRequest(batch_name="test_computer_jobs", items=generate_demo_jds()))
    graph = orchestrator.build_graph(JobGraphBuildRequest(batch_id=batch.batch_id, target_job_title="Java 后端工程师"))
    evolution = orchestrator.run_evolution(graph.job_id)
    session = orchestrator.start_assessment(
        "candidate_test",
        graph.job_id,
        "本科，3年Java后端经验。负责订单系统，使用Java、Spring Boot、MySQL、Redis、Docker和Kubernetes。",
    )
    session = orchestrator.answer_assessment(
        AssessmentAnswer(session_id=session.session_id, answer="我负责 Java、Spring Boot、Redis 和 MySQL 订单链路优化。")
    )
    session = orchestrator.answer_assessment(
        AssessmentAnswer(session_id=session.session_id, answer="我会先排查监控、日志、数据库和缓存，再进行降级止血。")
    )
    session = orchestrator.answer_assessment(
        AssessmentAnswer(session_id=session.session_id, answer="我会保护核心交易链路，回滚风险版本，再补充复盘。")
    )
    session = orchestrator.assessment_game_result(
        GameResultInput(
            session_id=session.session_id,
            events=[
                {"time": 1.2, "type": "allocate_resource", "value": "backend:3"},
                {"time": 2.3, "type": "allocate_resource", "value": "database:2"},
                {"time": 3.1, "type": "allocate_resource", "value": "cache:2"},
                {"time": 4.0, "type": "allocate_resource", "value": "observability:2"},
            ],
        )
    )
    profile = orchestrator.finalize_assessment(session.session_id).candidate_profile
    report = orchestrator.match_report(profile.candidate_id, graph.job_id)
    return batch, graph, evolution, session, profile, report


def test_full_enterprise_pipeline_runs():
    batch, graph, evolution, session, profile, report = run_demo_pipeline()

    assert len(batch.items) == 100
    assert graph.job_title == "Java 后端工程师"
    assert len(graph.skills) >= 5
    assert any(candidate["job_title"] == "AI Agent 工程师" for candidate in evolution.new_job_candidates)
    assert session.current_stage == "finalize_profile"
    assert profile.confidence >= 0.7
    assert report.score >= 55
    assert report.executive_summary


def test_graph_has_evidence_nodes_and_edges():
    _, graph, *_ = run_demo_pipeline()

    node_types = {node["type"] for node in graph.graph_nodes}
    assert {"job", "skill", "evidence"}.issubset(node_types)
    assert any(edge["label"] == "requires" for edge in graph.graph_edges)
    assert any(edge["label"] == "supported_by" for edge in graph.graph_edges)
