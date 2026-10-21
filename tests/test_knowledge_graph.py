from datetime import UTC, datetime

from agents.job_graph.knowledge_graph import KnowledgeGraphService
from agents.data.normalization import is_valid_skill
from contracts import CleanedDataItem


def job(
    source_id: str,
    platform: str,
    domain: str,
    title: str,
    skills: list[str],
    city: str = "北京",
) -> CleanedDataItem:
    content = f"负责{title}研发，要求掌握{'、'.join(skills)}，具备生产交付经验。"
    return CleanedDataItem(
        source_id=source_id, domain=domain, title=title, content=content, raw_content=content,
        quality_score=92, dedup_hash=source_id, source_platform=platform,
        source_url=f"https://example.com/{source_id}", company=f"企业{source_id}", city=city,
        skill_tags=skills, responsibilities=[f"负责{title}研发与交付"], published_at=datetime.now(UTC),
    )


def test_knowledge_graph_uses_only_live_recruitment_evidence():
    jobs = [
        job("boss-1", "boss", "人工智能", "AI Agent 工程师", ["Python", "LangGraph", "RAG"]),
        job("zl-1", "zhaopin", "人工智能", "大模型应用工程师", ["Python", "RAG", "向量数据库"]),
        job("manual-1", "企业岗位库", "人工智能", "测试岗位", ["Python"]),
    ]
    graph = KnowledgeGraphService().build(jobs, max_evidence=20)

    assert graph["data_policy"] == "recruitment_primary_live_only"
    assert graph["stats"]["source_jobs"] == 2
    assert set(graph["stats"]["sources"]) == {"boss", "zhaopin"}
    assert {node["type"] for node in graph["nodes"]} == {"domain", "job", "capability", "skill", "evidence"}
    evidence = [node for node in graph["nodes"] if node["type"] == "evidence"]
    assert evidence and all(node["sourceUrl"].startswith("https://example.com/") for node in evidence)
    assert all("manual-1" not in node["id"] for node in graph["nodes"])


def test_knowledge_graph_filters_domain_and_keeps_hierarchy_consistent():
    jobs = [
        job("boss-ai", "boss", "人工智能", "算法工程师", ["Python", "PyTorch"]),
        job("boss-iot", "boss", "物联网", "嵌入式工程师", ["C++", "RTOS"]),
    ]
    graph = KnowledgeGraphService().build(jobs, domain="物联网", max_evidence=10)
    ids = {node["id"] for node in graph["nodes"]}

    assert graph["stats"]["source_jobs"] == 1
    assert all(node["label"] != "人工智能" for node in graph["nodes"])
    assert all(edge["source"] in ids and edge["target"] in ids for edge in graph["edges"])


def test_career_galaxy_uses_real_jobs_and_builds_temporal_rings():
    first = job("boss-ai", "boss", "人工智能", "高级 AI Agent 工程师", ["Python", "RAG"])
    second = job("zl-ai", "zhaopin", "人工智能", "AI Agent 工程师", ["Python", "RAG"])
    first.collected_at = datetime(2026, 7, 17, 9, tzinfo=UTC)
    second.collected_at = datetime(2026, 7, 20, 10, tzinfo=UTC)
    first.published_at = first.collected_at
    second.published_at = second.collected_at
    first.experience_min_years = 5
    second.experience_min_years = 1

    graph = KnowledgeGraphService().build_career_galaxy([first, second], max_nodes=100)
    ids = {node["id"] for node in graph["nodes"]}
    job_nodes = [node for node in graph["nodes"] if node["nodeType"] == "job"]

    assert graph["layout"] == "career_galaxy_wormhole"
    assert graph["data_policy"] == "live_recruitment_current_plus_simulated_monthly_history"
    assert len(graph["layers"]) == 12
    assert graph["layers"][0]["label"] == "2025.08"
    assert graph["layers"][-1]["label"] == "2026.07"
    assert graph["layers"][-1]["isSimulated"] is False
    assert all(layer["isSimulated"] for layer in graph["layers"][:-1])
    assert {node["ringType"] for node in job_nodes} == {"inner", "middle"}
    assert {node["nodeType"] for node in graph["nodes"]} == {"family", "job", "skill"}
    assert all(node["sourceUrl"].startswith("https://example.com/") for node in job_nodes)
    assert all(link["source"] in ids and link["target"] in ids for link in graph["links"])


def test_career_galaxy_evolution_contains_explainable_skill_deltas():
    first = job("boss-old", "boss", "人工智能", "AI Agent 工程师", ["Python", "RAG"])
    second = job("boss-new", "boss", "人工智能", "AI Agent 工程师", ["Python", "LangGraph"])
    first.published_at = first.collected_at = datetime(2026, 7, 17, tzinfo=UTC)
    second.published_at = second.collected_at = datetime(2026, 7, 20, tzinfo=UTC)

    graph = KnowledgeGraphService().build_career_galaxy([first, second], max_nodes=100)
    evolution = [link for link in graph["links"] if link["type"] == "evolution"]

    assert len(evolution) == 11
    assert all({"addedSkills", "removedSkills", "risingSkills", "jobDelta"} <= link.keys() for link in evolution)
    assert any(link["addedSkills"] for link in evolution)
    simulated_nodes = [node for node in graph["nodes"] if node.get("isSimulated")]
    assert simulated_nodes
    assert all(not node.get("evidenceIds") for node in simulated_nodes)


def test_career_galaxy_deep_relations_link_jobs_skills_and_similar_jobs():
    jobs = [
        job("boss-agent-a", "boss", "人工智能", "AI Agent 工程师", ["Python", "RAG", "LangGraph"]),
        job("boss-agent-b", "boss", "人工智能", "AI Agent 开发工程师", ["Python", "RAG", "LangChain"]),
        job("zl-agent-c", "zhaopin", "人工智能", "大模型应用工程师", ["Python", "RAG", "向量数据库"]),
    ]
    for item in jobs:
        item.published_at = item.collected_at = datetime(2026, 7, 20, tzinfo=UTC)

    graph = KnowledgeGraphService().build_career_galaxy(
        jobs, max_nodes=100, deep_relations=True,
    )
    job_skill = [link for link in graph["links"] if link["type"] == "job_requires_skill"]
    similarities = [
        link for link in graph["links"]
        if link["type"] == "job_similarity" and link.get("relationScope") == "job_instance"
    ]

    assert graph["stats"]["job_skill_edges"] >= 6
    assert graph["stats"]["job_similarity_edges"] >= 1
    assert job_skill and all(link["evidenceIds"] for link in job_skill)
    assert similarities and all(len(link["sharedSkills"]) >= 2 for link in similarities)


def test_hierarchy_and_temporal_graph_keep_recruitment_evidence_ids():
    jobs = [
        job("boss-agent", "boss", "人工智能", "AI Agent 工程师", ["Python", "RAG", "LangGraph"]),
        job("zl-agent", "zhaopin", "人工智能", "AI Agent 工程师", ["Python", "RAG"]),
    ]
    service = KnowledgeGraphService()

    overview = service.build_hierarchy_level(jobs)
    domain_node = next(item for item in overview["children"] if item["label"] == "人工智能")
    families = service.build_hierarchy_level(jobs, parent_id=domain_node["id"])
    family = next(item for item in families["children"] if item["type"] == "job")
    temporal = service.build_career_galaxy(jobs, max_nodes=100)
    skill = next(item for item in temporal["nodes"] if item["nodeType"] == "skill")

    assert family["evidenceStatus"] == "verified_recruitment"
    assert set(family["evidenceIds"]) == {"boss-agent", "zl-agent"}
    assert skill["canPublishAbility"] is True
    assert skill["evidenceIds"]


def test_city_map_aggregates_real_jobs_and_builds_explainable_similarity():
    jobs = [
        job("bj-1", "boss", "人工智能", "AI Agent 工程师", ["Python", "RAG", "LangGraph"], "北京"),
        job("bj-2", "zhaopin", "人工智能", "大模型工程师", ["Python", "RAG", "PyTorch"], "北京"),
        job("sh-1", "boss", "人工智能", "AI 平台工程师", ["Python", "RAG", "Docker"], "上海"),
        job("sz-1", "zhaopin", "物联网", "嵌入式工程师", ["C++", "RTOS"], "深圳"),
        job("unknown", "boss", "人工智能", "算法工程师", ["Python"], "未知城市"),
    ]

    graph = KnowledgeGraphService().build_city_map(jobs, max_cities=20)
    cities = {item["name"]: item for item in graph["cities"]}

    assert graph["layout"] == "china_city_talent_map"
    assert graph["stats"]["source_jobs"] == 5
    assert graph["stats"]["mapped_jobs"] == 4
    assert set(cities) == {"北京", "上海", "深圳"}
    assert cities["北京"]["jobCount"] == 2
    assert cities["北京"]["dominantDomain"] == "人工智能"
    assert cities["北京"]["coord"] == (116.41, 39.9)
    assert any(
        {link["source"], link["target"]} == {"北京", "上海"}
        and "Python" in link["sharedSkills"]
        for link in graph["links"]
    )


def test_city_drilldown_returns_only_the_requested_graph_level():
    jobs = [
        job("bj-1", "boss", "人工智能", "AI Agent 工程师", ["Python", "RAG", "LangGraph"], "北京"),
        job("bj-2", "zhaopin", "人工智能", "大模型应用工程师", ["Python", "RAG"], "北京"),
        job("bj-3", "zhaopin", "大数据", "实时计算工程师", ["Java", "Flink"], "北京"),
        job("sh-1", "boss", "人工智能", "AI Agent 工程师", ["Python"], "上海"),
    ]
    service = KnowledgeGraphService()

    domains = service.build_city_drilldown(jobs, city="北京市")
    assert domains["level"] == "domain"
    assert {item["name"] for item in domains["children"]} == {"人工智能", "大数据"}
    assert domains["summary"]["jobCount"] == 3

    families = service.build_city_drilldown(jobs, city="北京", domain="人工智能")
    assert families["level"] == "family"
    assert families["path"][-1] == {"type": "domain", "name": "人工智能"}

    skills = service.build_city_drilldown(
        jobs, city="北京", domain="人工智能", family="AI Agent 工程师",
    )
    assert skills["level"] == "skill"
    assert any(item["name"] == "LangGraph" for item in skills["children"])

    evidence = service.build_city_drilldown(
        jobs, city="北京", domain="人工智能", family="AI Agent 工程师", skill="Python",
    )
    assert evidence["level"] == "evidence"
    assert [item["id"] for item in evidence["children"]] == ["bj-1"]
    assert evidence["children"][0]["sourceUrl"].endswith("/bj-1")
def test_published_skill_gate_rejects_recruitment_benefit_noise():
    assert is_valid_skill("Python") is True
    assert is_valid_skill("同事很nice") is False
    assert is_valid_skill("五险一金") is False
    assert is_valid_skill("绩效奖金") is False
