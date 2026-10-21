from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from agents.llm import OpenAICompatibleClient
from contracts import CleanedDataBatch, JobGraph, SkillEvidence, SkillRequirement
from core.evidence import evidence_confidence, snippet_for_skill


SKILL_CATALOG = {
    "Java": ("language", "advanced"),
    "Spring Boot": ("framework", "advanced"),
    "MySQL": ("database", "intermediate"),
    "Redis": ("database", "intermediate"),
    "消息队列": ("middleware", "intermediate"),
    "微服务": ("architecture", "advanced"),
    "Kubernetes": ("cloud_native", "intermediate"),
    "Docker": ("cloud_native", "intermediate"),
    "Python": ("language", "intermediate"),
    "RAG": ("ai", "advanced"),
    "LangGraph": ("ai", "intermediate"),
    "向量数据库": ("ai", "intermediate"),
    "Prompt Engineering": ("ai", "intermediate"),
    "FastAPI": ("backend", "intermediate"),
    "Spark": ("big_data", "intermediate"),
    "Flink": ("big_data", "advanced"),
    "Kafka": ("middleware", "intermediate"),
    "Hive": ("big_data", "intermediate"),
    "MQTT": ("iot", "intermediate"),
    "嵌入式 Linux": ("iot", "intermediate"),
    "Prometheus": ("observability", "intermediate"),
    "自动化测试": ("testing", "intermediate"),
    "性能测试": ("testing", "intermediate"),
    "Spring Cloud": ("framework", "advanced"),
    "可观测性": ("observability", "intermediate"),
    "CI/CD": ("engineering", "intermediate"),
    "SQL": ("data", "intermediate"),
    "工具调用": ("ai", "intermediate"),
    "评测体系": ("ai", "intermediate"),
}

CAPABILITY_LABELS = {
    "language": "编程语言", "framework": "开发框架", "database": "数据存储", "middleware": "中间件",
    "architecture": "架构设计", "cloud_native": "云原生", "ai": "人工智能", "backend": "后端工程",
    "big_data": "大数据工程", "iot": "智能物联", "observability": "稳定性工程", "testing": "质量工程",
    "engineering": "工程效能", "data": "数据能力",
}

TOOL_NAMES = {"Spring Boot", "MySQL", "Redis", "Kubernetes", "Docker", "FastAPI", "Spark", "Flink", "Kafka", "Hive", "Prometheus", "LangGraph"}


class JobGraphAgent:
    def __init__(self, llm: OpenAICompatibleClient | None = None) -> None:
        self.llm = llm or OpenAICompatibleClient()

    def run(self, batch: CleanedDataBatch, target_job_title: str = "Java 后端工程师") -> JobGraph:
        relevant = [item for item in batch.items if target_job_title[:4] in item.title or item.title in target_job_title]
        if not relevant:
            relevant = batch.items[: min(20, len(batch.items))]
        llm_analysis = self._analyze_with_llm(relevant, target_job_title)
        catalog = dict(SKILL_CATALOG)
        by_source = {item.source_id: item for item in relevant}
        for item in llm_analysis.get("skills", []):
            if not isinstance(item, dict) or not item.get("name"):
                continue
            name = str(item["name"]).strip()
            evidence_items = [
                by_source[str(source_id)]
                for source_id in item.get("source_ids", [])
                if str(source_id) in by_source
            ]
            if not evidence_items or not any(
                name.casefold() in f"{source.content} {' '.join(source.skill_tags)}".casefold()
                for source in evidence_items
            ):
                continue
            catalog[name] = (
                str(item.get("category", "engineering")),
                self._normalize_level(item.get("required_level")),
            )
        skill_hits: dict[str, list] = defaultdict(list)
        for item in relevant:
            for skill in catalog:
                if skill in item.content:
                    skill_hits[skill].append(item)
        for skill in llm_analysis.get("skills", []):
            if not isinstance(skill, dict) or not skill.get("name"):
                continue
            name = str(skill["name"])
            for source_id in skill.get("source_ids", []):
                if str(source_id) in by_source and by_source[str(source_id)] not in skill_hits[name]:
                    skill_hits[name].append(by_source[str(source_id)])
        if not skill_hits:
            for item in relevant:
                for token in re.findall(r"[A-Za-z][A-Za-z0-9+#. -]{1,24}|[\u4e00-\u9fff]{2,8}", item.content):
                    if token in catalog:
                        skill_hits[token].append(item)
        total = max(len(relevant), 1)
        skills: list[SkillRequirement] = []
        for skill, items in sorted(skill_hits.items(), key=lambda kv: len(kv[1]), reverse=True)[:14]:
            category, level = catalog[skill]
            avg_quality = sum(i.quality_score for i in items) / len(items)
            importance = "required" if len(items) / total >= 0.35 else "preferred"
            confidence = evidence_confidence(len(items), avg_quality)
            evidence = [
                SkillEvidence(
                    source_id=i.source_id,
                    source_type=i.source_type,
                    snippet=self._evidence_snippet(i, skill),
                    confidence=min(confidence, 0.98),
                )
                for i in items[:3]
            ]
            skills.append(
                SkillRequirement(
                    skill_id=self._slug(skill),
                    name=skill,
                    category=category,
                    required_level=level,
                    importance=importance,
                    evidence=evidence,
                    confidence=confidence,
                )
            )
        responsibilities = [str(item) for item in llm_analysis.get("responsibilities", []) if item][:12] or self._responsibilities(relevant)
        domain = self._domain(relevant)
        job_id = self._slug(target_job_title)
        scenarios = [str(item) for item in llm_analysis.get("scenarios", []) if item][:6] or self._scenarios(domain)
        nodes, edges = self._graph(job_id, target_job_title, skills, responsibilities, scenarios)
        categories = sorted({s.category for s in skills})
        tools = [{"name": s.name, "category": s.category, "confidence": s.confidence} for s in skills if s.name in TOOL_NAMES]
        return JobGraph(
            job_id=job_id,
            job_title=target_job_title,
            domain=domain,
            responsibilities=responsibilities,
            skills=skills,
            scenarios=scenarios,
            capability_domains=[{"id": f"cap_{c}", "name": CAPABILITY_LABELS.get(c, c), "skill_count": sum(s.category == c for s in skills)} for c in categories],
            tools=tools,
            evidence_summary={
                "source_count": len({ev.source_id for skill in skills for ev in skill.evidence}),
                "evidence_count": sum(len(skill.evidence) for skill in skills),
                "average_confidence": round(sum(s.confidence for s in skills) / max(len(skills), 1), 2),
                "provider_status": llm_analysis.get("provider_status", self.llm.status()),
            },
            graph_nodes=nodes,
            graph_edges=edges,
        )

    def _analyze_with_llm(self, items, target_job_title: str) -> dict:
        fallback = {"skills": [], "responsibilities": [], "scenarios": []}
        if not self.llm.configured:
            return {**fallback, "provider_status": self.llm.status()}
        payload = [
            {
                "source_id": item.source_id,
                "title": item.title,
                "skill_tags": item.skill_tags,
                "responsibilities": item.responsibilities,
                "requirements": item.requirements,
                "evidence_segments": item.evidence_segments[:24],
                "content": item.content[:4000],
            }
            for item in items[:30]
        ]
        result = self.llm.generate_json(
            system_prompt=(
                "你是岗位能力图谱抽取 Agent。只输出 JSON 对象，字段为 skills、responsibilities、scenarios。"
                "skills 每项包含 name、category、required_level、source_ids；category 使用 language/framework/database/middleware/"
                "architecture/cloud_native/ai/backend/big_data/iot/observability/testing/engineering/data。"
                "每项必须由 source_ids 指向输入证据，不得生成无来源技能。"
            ),
            user_prompt=json.dumps({"target_job_title": target_job_title, "documents": payload}, ensure_ascii=False),
            fallback=fallback,
        )
        return {**fallback, **result.data, "provider_status": result.provider_status}

    @staticmethod
    def _normalize_level(value) -> str:
        text = str(value or "intermediate").casefold()
        aliases = {
            "beginner": "basic", "junior": "basic", "基础": "basic",
            "proficient": "advanced", "senior": "advanced", "熟练": "advanced",
            "master": "expert", "精通": "expert",
        }
        normalized = aliases.get(text, text)
        return normalized if normalized in {"basic", "intermediate", "advanced", "expert"} else "intermediate"

    def _domain(self, items) -> str:
        if not items:
            return "计算机岗位"
        return Counter(i.domain for i in items).most_common(1)[0][0]

    def _slug(self, text: str) -> str:
        mapping = {" ": "_", "/": "_", "：": "_"}
        out = text.lower()
        for old, new in mapping.items():
            out = out.replace(old, new)
        return re.sub(r"[^a-z0-9_\u4e00-\u9fff]+", "", out)

    def _responsibilities(self, items) -> list[str]:
        extracted = [responsibility for item in items for responsibility in item.responsibilities]
        return list(dict.fromkeys(extracted))[:12] or [
            "负责计算机相关业务系统设计、开发与交付",
            "参与性能优化、故障排查和工程质量建设",
            "沉淀可复用技术方案并协同团队推进落地",
        ]

    def _evidence_snippet(self, item, skill: str) -> str:
        for segment in item.evidence_segments:
            segment_skills = segment.get("skills") or []
            text = str(segment.get("text") or "")
            if skill in segment_skills or skill.casefold() in text.casefold():
                return text[:500]
        return snippet_for_skill(item.content, skill)

    def _scenarios(self, domain: str) -> list[str]:
        if "AI" in domain or "大模型" in domain:
            return ["企业知识问答", "智能流程自动化", "模型效果评测"]
        if "大数据" in domain:
            return ["实时数据处理", "企业数据仓库", "数据质量治理"]
        return ["核心业务高并发", "云原生服务交付", "线上故障应急"]

    def _graph(self, job_id: str, title: str, skills: list[SkillRequirement], responsibilities: list[str], scenarios: list[str]):
        nodes = [{"id": job_id, "label": title, "type": "job", "score": 1}]
        edges = []
        categories = sorted({s.category for s in skills})
        for category in categories:
            cid = f"cap_{category}"
            nodes.append({"id": cid, "label": CAPABILITY_LABELS.get(category, category), "type": "capability_domain", "score": 0.8})
            edges.append({"source": job_id, "target": cid, "label": "requires"})
        for skill in skills:
            nodes.append({"id": skill.skill_id, "label": skill.name, "type": "skill", "score": skill.confidence})
            edges.append({"source": f"cap_{skill.category}", "target": skill.skill_id, "label": skill.importance})
            if skill.name in TOOL_NAMES:
                tid = f"tool_{skill.skill_id}"
                nodes.append({"id": tid, "label": skill.name, "type": "tool", "score": skill.confidence})
                edges.append({"source": skill.skill_id, "target": tid, "label": "implemented_with"})
            for ev in skill.evidence[:1]:
                eid = f"ev_{ev.source_id}_{skill.skill_id}"
                nodes.append({"id": eid, "label": ev.source_id, "type": "evidence", "score": ev.confidence, "snippet": ev.snippet})
                edges.append({"source": skill.skill_id, "target": eid, "label": "supported_by"})
        for index, responsibility in enumerate(responsibilities):
            rid = f"resp_{job_id}_{index}"
            nodes.append({"id": rid, "label": responsibility, "type": "responsibility", "score": 0.85})
            edges.append({"source": job_id, "target": rid, "label": "owns"})
            if skills:
                skill = skills[index % len(skills)]
                source = f"tool_{skill.skill_id}" if skill.name in TOOL_NAMES else skill.skill_id
                edges.append({"source": source, "target": rid, "label": "enables"})
        for index, scenario in enumerate(scenarios):
            sid = f"scene_{job_id}_{index}"
            nodes.append({"id": sid, "label": scenario, "type": "scenario", "score": 0.8})
            edges.append({"source": f"resp_{job_id}_{index % len(responsibilities)}", "target": sid, "label": "applied_in"})
            evidence_nodes = [node for node in nodes if node["type"] == "evidence"]
            if evidence_nodes:
                edges.append({"source": sid, "target": evidence_nodes[index % len(evidence_nodes)]["id"], "label": "validated_by"})
        return nodes, edges
